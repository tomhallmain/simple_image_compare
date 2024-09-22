import json
import os
import sys

from PIL import Image
import pprint

from utils.config import config

has_imported_sd_prompt_reader = False
try:
    if config.sd_prompt_reader_loc is not None and os.path.isdir(config.sd_prompt_reader_loc):
        sys.path.insert(0, config.sd_prompt_reader_loc)
        from sd_prompt_reader.image_data_reader import ImageDataReader
        has_imported_sd_prompt_reader = True
except Exception as e:
    print(e)
    print("Failed to import SD Prompt Reader!")


class ImageDataExtractor:
    CLASS_TYPE = "class_type"
    INPUTS = "inputs"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    TAGS_KEY = "SIC_TAGS"
    COMFYUI_PROMPT_KEY = "prompt"
    A1111_PARAMS_KEY = "parameters"
    RELATED_IMAGE_KEY = "related_image"

    def __init__(self):
        pass

    def is_xl(self, image_path):
        width, height = Image.open(image_path).size
        return width > 768 and height > 768

    def equals_resolution(self, image_path, ex_width=512, ex_height=512):
        width, height = Image.open(image_path).size
        return width == ex_width and height == ex_height

    def higher_than_resolution(self, image_path, max_width=512, max_height=512, inclusive=True):
        width, height = Image.open(image_path).size
        if max_width:
            if inclusive:
                if max_width > width:
                    return False
            elif max_width >= width:
                return False
        if max_height:
            if inclusive:
                if max_height > height:
                    return False
            elif max_height >= height:
                return False
        return True

    def lower_than_resolution(self, image_path, max_width=512, max_height=512, inclusive=True):
        width, height = Image.open(image_path).size
        if max_width:
            if inclusive:
                if max_width < width:
                    return False
            elif max_width <= width:
                return False
        if max_height:
            if inclusive:
                if max_height < height:
                    return False
            elif max_height <= height:
                return False
        return True

    def get_raw_metadata_text(self, image_path):
        info = Image.open(image_path).info
        if not isinstance(info, dict):
            return None
        return pprint.pformat(info)

    def extract_prompt(self, image_path):
        info = Image.open(image_path).info
        if isinstance(info, dict):
            if ImageDataExtractor.COMFYUI_PROMPT_KEY in info:
                prompt = json.loads(info[ImageDataExtractor.COMFYUI_PROMPT_KEY])
                return prompt
            elif ImageDataExtractor.A1111_PARAMS_KEY in info:
#                print(info[ImageDataExtractor.A1111_PARAMS_KEY])
#                print("skipping unhandled Automatic1111 image info")
                pass
            else:
#                print(info)
#                print("Unhandled exif data: " + image_path)
                pass
        else:
            print("Exif data not found: " + image_path)
        return None

    def get_input_by_node_id(self, image_path, node_id, input_name):
        prompt = self.extract_prompt(image_path)
        if not prompt or node_id not in prompt:
            return None
        return prompt[node_id]["inputs"][input_name]

    def get_input_by_class_type(self, image_path, class_type, input_name):
        prompt = self.extract_prompt(image_path)
        if not prompt:
            return None
        for node_id, node in prompt.items():
            if "class_type" in node and class_type == node["class_type"]:
                return node["inputs"][input_name]
        raise Exception("Could not find node with class type " + class_type)

    def extract_tags(self, image_path):
        info = Image.open(image_path).info
        if isinstance(info, dict):
            if ImageDataExtractor.TAGS_KEY in info:
                tags = json.loads(info[ImageDataExtractor.TAGS_KEY])
                return tags
            else:
#                print(info)
                # TODO IPTC Info handling maybe.
                pass
        else:
            print("Exif data not found: " + image_path)
        return None

    ## TODO TODO
    def set_tags(self, image_path, tags):
        image = Image.open(image_path)
        new_info = {}
        new_image_path = self.new_image_with_info(image, new_info, image_path=image_path, image_copy_path=None, target_dir=None)

    def copy_prompt_to_file(self, image_path, prompt_file_path):
        prompt = self.extract_prompt(image_path)
        with open(prompt_file_path, "w") as store:
            json.dump(prompt, store, indent=2)

    def extract(self, image_path):
        positive = ""
        negative = ""
        prompt_dicts = {}
        node_inputs = {}
        prompt = self.extract_prompt(image_path)

        if prompt is not None:
            for k, v in prompt.items():
                if ImageDataExtractor.CLASS_TYPE in v and ImageDataExtractor.INPUTS in v:
                    # print(v[ImageDataExtractor.CLASS_TYPE])
                    if v[ImageDataExtractor.CLASS_TYPE] == "CLIPTextEncode":
                        prompt_dicts[k] = v[ImageDataExtractor.INPUTS]["text"]
                    elif v[ImageDataExtractor.CLASS_TYPE] == "ImpactWildcardProcessor":
                        positive = v[ImageDataExtractor.INPUTS]["populated_text"]
                    elif v[ImageDataExtractor.CLASS_TYPE] == "KSampler":
                        node_inputs[ImageDataExtractor.POSITIVE] = v[ImageDataExtractor.INPUTS][ImageDataExtractor.POSITIVE][0]
                        node_inputs[ImageDataExtractor.NEGATIVE] = v[ImageDataExtractor.INPUTS][ImageDataExtractor.NEGATIVE][0]

            if positive == "":
                positive = prompt_dicts.get(node_inputs[ImageDataExtractor.POSITIVE], "")
            negative = prompt_dicts.get(node_inputs[ImageDataExtractor.NEGATIVE], "")
            # print(f"Positive: \"{positive}\"")
            # print(f"Negative: \"{negative}\"")

        return (positive, negative)

    def get_models(self, image_path):
        prompt = self.extract_prompt(image_path)
        models = []
        loras = []

        if prompt is not None:
            for k, v in prompt.items():
                if ImageDataExtractor.CLASS_TYPE in v and ImageDataExtractor.INPUTS in v:
                    # print(v[ImageDataExtractor.CLASS_TYPE])
                    if "Checkpoint" in v[ImageDataExtractor.CLASS_TYPE] and "ckpt_name" in v[ImageDataExtractor.INPUTS]:
                        ckpt_name = v[ImageDataExtractor.INPUTS]["ckpt_name"]
                        if "." in ckpt_name:
                            ckpt_name = ckpt_name[:ckpt_name.rfind(".")]
                        models.append(ckpt_name)
                    elif "Lora" in v[ImageDataExtractor.CLASS_TYPE] and "lora_name" in v[ImageDataExtractor.INPUTS]:
                        strength_model = 0
                        strength_clip = 0
                        if "strength_model" in v[ImageDataExtractor.INPUTS]:
                            strength_model = v[ImageDataExtractor.INPUTS]["strength_model"]
                        if "strength_clip" in v[ImageDataExtractor.INPUTS]:
                            strength_clip = v[ImageDataExtractor.INPUTS]["strength_clip"]
                        if strength_model == 0 and strength_clip == 0:
                            continue
                        lora_name = v[ImageDataExtractor.INPUTS]["lora_name"]
                        if  "." in lora_name:
                            lora_name = lora_name[:lora_name.rfind(".")]
                        loras.append(lora_name)

        return (models, loras)


    def uses_load_images(self, image_path, control_net_image_paths=[]):
        if not control_net_image_paths or len(control_net_image_paths) == 0:
            raise Exception("Control net image not provided.")
        prompt = self.extract_prompt(image_path)

        if prompt is not None:
            for v in prompt.values():
                if ImageDataExtractor.CLASS_TYPE in v:
                    if v[ImageDataExtractor.CLASS_TYPE] == "LoadImage" and ImageDataExtractor.INPUTS in v:
                        loaded_image = v[ImageDataExtractor.INPUTS]["image"]
                        for control_net_image_path in control_net_image_paths:
                            if loaded_image == control_net_image_path:
                                print(f"Found control net image - Image ({image_path}) Control Net ({control_net_image_path})")
                                return control_net_image_path
        return None

    def copy_without_exif(self, image_path, image_copy_path=None, target_dir=None):
        image = Image.open(image_path)

        # strip exif
        new_image_path = self.new_image_with_info(image, image_path=image_path, image_copy_path=image_copy_path, target_dir=target_dir)
        print("Copied image without exif data to: " + new_image_path)

    def new_image_with_info(self, image, info=None, image_path=None, image_copy_path=None, target_dir=None, append="_"):
        data = list(image.getdata())
        new_image = Image.new(image.mode, image.size)
        new_image.putdata(data)

        if info is not None:
            new_image.info = info

        if image_copy_path is not None:
            new_image_path = image_copy_path
        else:
            if image_path is None:
                raise Exception("Image path was not passed to new_image_with_data")
            dirpath = os.path.dirname(image_path) if target_dir is None else target_dir
            basename, extension = os.path.splitext(os.path.basename(image_path))
            if target_dir is None:
                basename += append
            new_image_path = os.path.join(dirpath, basename + extension)

        new_image.save(new_image_path)
        new_image.close() # close the file handler after saving the image.
        return new_image_path


    def print_imageinfo(self, image_path):
        info = Image.open(image_path).info
        print("Image info for image: " + image_path)
        pprint.pprint(info)

    def print_prompt(self, image_path):
        prompt = self.extract_prompt(image_path)
        print("Prompt for image: " + image_path)
        pprint.pprint(prompt)

    def dump_prompt(self, image_path):
        prompt = self.extract_prompt(image_path)
        with open("extracted_prompt.json", "w") as store:
            json.dump(prompt, store, indent=2)

    def get_image_data_reader(self, image_path):
        if not has_imported_sd_prompt_reader:
            raise Exception("Stable diffusion prompt reader failed to import. Please check log and config.json file.")
        return ImageDataReader(image_path)

    def get_image_prompts_and_models(self, image_path):
        positive = "(Unable to parse image prompt information for this file.)"
        negative = ""

        if has_imported_sd_prompt_reader:
            try:
                image_data = self.get_image_data_reader(image_path)
                if image_data.tool:
                    if image_data.is_sdxl:
                        positive = image_data.positive_sdxl
                        negative = image_data.negative_sdxl
                    else:
                        positive = image_data.positive
                        negative = image_data.negative
                    if not positive or positive.strip() == "":
                        try:
                            positive, negative = self.extract(image_path)
                        except Exception as e:
                           pass
                        if not positive or positive.strip() == "":
                            positive = "(No prompt found for this file.)"
            except Exception as e:
#                print(e)
                pass

        models = []
        loras = []
        try:
            models, loras = self.get_models(image_path)
        except Exception as e:
            pass

        return positive, negative, models, loras

    def get_related_image_path(self, image_path, node_id="LoadImage"):
        use_class_type = True
        try:
            int(node_id)
            use_class_type = False
        except ValueError:
            pass
        try:
            if use_class_type:
                related_image_path = image_data_extractor.get_input_by_class_type(image_path, node_id, "image")
            else:
                related_image_path = image_data_extractor.get_input_by_node_id(image_path, node_id, "image")
        except Exception:
            related_image_path = None
        if related_image_path is None:
            info = Image.open(image_path).info
            if ImageDataExtractor.RELATED_IMAGE_KEY in info:
                return str(info[ImageDataExtractor.RELATED_IMAGE_KEY])
        return related_image_path

image_data_extractor = ImageDataExtractor()
