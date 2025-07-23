from enum import Enum
import json
import os
import re
import sys

from PIL import Image
import pprint

from utils.config import config
from utils.logging_setup import get_logger

logger = get_logger("image_data_extractor")

has_imported_sd_prompt_reader = False
try:
    if config.sd_prompt_reader_loc is not None and os.path.isdir(config.sd_prompt_reader_loc):
        sys.path.insert(0, config.sd_prompt_reader_loc)
        from sd_prompt_reader.image_data_reader import ImageDataReader
        has_imported_sd_prompt_reader = True
except Exception as e:
    logger.error(e)
    logger.error("Failed to import SD Prompt Reader!")


class SoftwareType(Enum):
    COMFYUI = "comfyui"
    A1111 = "a1111"


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
            if ImageDataExtractor.A1111_PARAMS_KEY in info:
                return self._build_a1111_prompt_info_object(info[ImageDataExtractor.A1111_PARAMS_KEY]), SoftwareType.A1111
            if ImageDataExtractor.COMFYUI_PROMPT_KEY in info:
                prompt = json.loads(info[ImageDataExtractor.COMFYUI_PROMPT_KEY])
                return prompt, SoftwareType.COMFYUI
            else:
                logger.debug(info.keys())
                logger.debug("Unhandled exif data: " + image_path)
                pass
        else:
            logger.warning("Exif data not found: " + image_path)
        return None, None

    def get_input_by_node_id(self, image_path, node_id, input_name):
        prompt, software_type = self.extract_prompt(image_path)
        if not prompt or software_type != SoftwareType.COMFYUI or node_id not in prompt:
            return None
        return prompt[node_id]["inputs"][input_name]

    def get_input_by_class_type(self, image_path, class_type, input_name):
        prompt, software_type = self.extract_prompt(image_path)
        if not prompt or software_type != SoftwareType.COMFYUI:
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
#                logger.debug(info)
                # TODO IPTC Info handling maybe.
                pass
        else:
            logger.warning("Exif data not found: " + image_path)
        return None

    ## TODO TODO
    def set_tags(self, image_path, tags):
        image = Image.open(image_path)
        new_info = {}
        new_image_path = self.new_image_with_info(image, new_info, image_path=image_path, image_copy_path=None, target_dir=None)

    def copy_prompt_to_file(self, image_path, prompt_file_path):
        prompt, _ = self.extract_prompt(image_path)
        with open(prompt_file_path, "w") as store:
            json.dump(prompt, store, indent=2)

    def extract(self, image_path):
        positive = None
        negative = None
        prompt_dicts = {}
        node_inputs = {}
        prompt, software_type = self.extract_prompt(image_path)

        if software_type == SoftwareType.COMFYUI:
            for k, v in prompt.items():
                if ImageDataExtractor.CLASS_TYPE in v and ImageDataExtractor.INPUTS in v:
                    # logger.debug(v[ImageDataExtractor.CLASS_TYPE])
                    if v[ImageDataExtractor.CLASS_TYPE] == "CLIPTextEncode":
                        prompt_dicts[k] = v[ImageDataExtractor.INPUTS]["text"]
                    elif v[ImageDataExtractor.CLASS_TYPE] == "ImpactWildcardProcessor":
                        positive = v[ImageDataExtractor.INPUTS]["populated_text"]
                    elif v[ImageDataExtractor.CLASS_TYPE] == "KSampler":
                        node_inputs[ImageDataExtractor.POSITIVE] = v[ImageDataExtractor.INPUTS][ImageDataExtractor.POSITIVE][0]
                        node_inputs[ImageDataExtractor.NEGATIVE] = v[ImageDataExtractor.INPUTS][ImageDataExtractor.NEGATIVE][0]

            if positive is None or positive.strip() == "":
                positive = prompt_dicts.get(node_inputs[ImageDataExtractor.POSITIVE], "")
            negative = prompt_dicts.get(node_inputs[ImageDataExtractor.NEGATIVE], "")
            # logger.debug(f"Positive: \"{positive}\"")
            # logger.debug(f"Negative: \"{negative}\"")

        return (positive, negative)

    def extract_with_sd_prompt_reader(self, image_path):
        positive = None
        negative = None
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
        except Exception as e:
            # logger.warning(e)
            pass
        return positive, negative

    def get_models(self, image_path):
        models = []
        loras = []
        prompt, software_type = self.extract_prompt(image_path)
        if prompt is None or software_type is None:
            return models, loras

        if software_type == SoftwareType.COMFYUI:
            for k, v in prompt.items():
                if ImageDataExtractor.CLASS_TYPE in v and ImageDataExtractor.INPUTS in v:
                    # logger.debug(v[ImageDataExtractor.CLASS_TYPE])
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
        elif software_type == SoftwareType.A1111:
            models, loras = [prompt["Model"]], prompt["Loras"]
        else:
            raise Exception("Unhandled software type: " + software_type)

        return (models, loras)


    def uses_load_images(self, image_path, control_net_image_paths=[]):
        if not control_net_image_paths or len(control_net_image_paths) == 0:
            raise Exception("Control net image not provided.")
        prompt, software_type = self.extract_prompt(image_path)

        if software_type == SoftwareType.COMFYUI:
            for v in prompt.values():
                if ImageDataExtractor.CLASS_TYPE in v:
                    if v[ImageDataExtractor.CLASS_TYPE] == "LoadImage" and ImageDataExtractor.INPUTS in v:
                        loaded_image = v[ImageDataExtractor.INPUTS]["image"]
                        for control_net_image_path in control_net_image_paths:
                            if loaded_image == control_net_image_path:
                                logger.info(f"Found control net image - Image ({image_path}) Control Net ({control_net_image_path})")
                                return control_net_image_path
        return None

    def copy_without_exif(self, image_path, image_copy_path=None, target_dir=None):
        image = Image.open(image_path)

        # strip exif
        new_image_path = self.new_image_with_info(image, image_path=image_path, image_copy_path=image_copy_path, target_dir=target_dir)
        logger.info("Copied image without exif data to: " + new_image_path)

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
        logger.info("Image info for image: " + image_path)
        pprint.pprint(info)

    def print_prompt(self, image_path):
        prompt, software_type = self.extract_prompt(image_path)
        logger.info("Prompt for image: " + image_path + " (" + str(software_type) + ")")
        pprint.pprint(prompt)

    def dump_prompt(self, image_path):
        prompt, _ = self.extract_prompt(image_path)
        with open("extracted_prompt.json", "w") as store:
            json.dump(prompt, store, indent=2)

    def get_image_data_reader(self, image_path):
        if not has_imported_sd_prompt_reader:
            raise Exception("Stable diffusion prompt reader failed to import. Please check log and config.json file.")
        return ImageDataReader(image_path)

    def get_image_prompts_and_models(self, image_path):
        if has_imported_sd_prompt_reader:
            positive, negative = self.extract_with_sd_prompt_reader(image_path)
        else:
            positive, negative = self.extract(image_path)
        if positive is None or positive.strip() == "":
            positive = "(Unable to parse image prompt information for this file.)"
        if negative is None or negative.strip() == "":
            negative = ""

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

    def _build_a1111_prompt_info_object(self, prompt_text):
        negative_prompt = "Negative prompt: "
        steps = "Steps: "
        sampler = "Sampler: "
        cfg = "CFG scale: "
        seed = "Seed: "
        size = "Size: "
        model_hash = "Model hash: "
        model = "Model: "
        denoising = "Denoising strength: "
        lora_hash = "Lora hashes: "
        version = "Version: "
        prompt_info = {}
        prompt_info["Positive prompt"] = prompt_text[:prompt_text.rfind(negative_prompt)]
        prompt_text = prompt_text[prompt_text.rfind(negative_prompt):]
        all_keys = [negative_prompt, steps, sampler, cfg, seed, size, model_hash, model, denoising, lora_hash, version]
        for i in range(len(all_keys)):
            key = all_keys[i]
            next_key = all_keys[i + 1] if i < (len(all_keys) - 1) else None
            if key in prompt_text:
                value = prompt_text[len(key):prompt_text.rfind(next_key)] if next_key is not None else prompt_text[len(key):]
                if len(value) > 0:
                    value = value.strip()
                    if value.endswith(","):
                        value = value[:-1]
                    if value.startswith("\"") and value.endswith("\""):
                        value = value[1:-1]
                prompt_info[key.strip().replace(":", "")] = value
                # print("____")
                # print(key)
                # print(value)
                # print(prompt_text)
                if next_key is not None:
                    prompt_text = prompt_text[prompt_text.rfind(next_key):]
        prompt_info["Positive prompt"], prompt_info["Loras"] = self._extract_loras_from_a1111_prompt(prompt_info["Positive prompt"])
        return prompt_info

    def _extract_loras_from_a1111_prompt(self, prompt_text):
        actual_prompt = prompt_text
        loras = []
        lora_tag_pattern = r"<lora:[A-Za-z0-9\-]+:[0-9\.]+(:[0-9\.]+)?>"
        first_lora_tag_match = re.search(lora_tag_pattern, prompt_text)
        if first_lora_tag_match is not None:
            actual_prompt = prompt_text[:first_lora_tag_match.start()].strip()
            for match in re.finditer(lora_tag_pattern, prompt_text):
                lora_tag = match.group(0)[6:-1]
                lora_name = lora_tag[:lora_tag.index(":")]
                # print(lora_name)
                loras.append(lora_name)
        return actual_prompt, loras

image_data_extractor = ImageDataExtractor()

