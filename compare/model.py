from PIL import Image
import torch
import clip
from transformers import AutoModel, AutoProcessor, FlavaProcessor, FlavaModel

from image.frame_cache import FrameCache
from utils.config import config

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load(config.clip_model, device=device)

# Lazy initialization variables for SIGLIP
_siglip_model = None
_siglip_processor = None

# Lazy initialization variables for FLAVA
_flava_model = None
_flava_processor = None

def _get_siglip_model():
    global _siglip_model
    if _siglip_model is None:
        _siglip_model = AutoModel.from_pretrained("google/siglip-base-patch16-224").to(device)
    return _siglip_model

def _get_siglip_processor():
    global _siglip_processor
    if _siglip_processor is None:
        _siglip_processor = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
    return _siglip_processor

def _get_flava_model():
    global _flava_model
    if _flava_model is None:
        _flava_model = FlavaModel.from_pretrained("facebook/flava-full").to(device)
    return _flava_model

def _get_flava_processor():
    global _flava_processor
    if _flava_processor is None:
        _flava_processor = FlavaProcessor.from_pretrained("facebook/flava-full")
    return _flava_processor

def image_embeddings(image_path):
    try:
     image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    except Exception as e:
        image_path = FrameCache.get_image_path(image_path)
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model.encode_image(image)
        embedding /= embedding.norm(dim=-1, keepdim=True)
        return embedding.tolist()[0]


def text_embeddings(text):
    tokens = clip.tokenize([text]).to(device)
    with torch.no_grad():
        embedding = model.encode_text(tokens).float()
        embedding /= embedding.norm(dim=-1, keepdim=True)
        return embedding.tolist()[0]


def image_embeddings_siglip(image_path):
    try:
        image = Image.open(image_path)
    except Exception as e:
        image_path = FrameCache.get_image_path(image_path)
        image = Image.open(image_path)
    
    # Process image with SIGLIP processor
    inputs = _get_siglip_processor()(images=image, return_tensors="pt").to(device)
    
    with torch.no_grad():
        # Get image features using SIGLIP model
        outputs = _get_siglip_model().get_image_features(**inputs)
        # Normalize the embeddings
        outputs = outputs / outputs.norm(dim=-1, keepdim=True)
        return outputs.tolist()[0]


def text_embeddings_siglip(text):
    # Process text with SIGLIP processor
    inputs = _get_siglip_processor()(text=[text], padding="max_length", return_tensors="pt").to(device)
    
    with torch.no_grad():
        # Get text features using SIGLIP model
        outputs = _get_siglip_model().get_text_features(**inputs)
        # Normalize the embeddings
        outputs = outputs / outputs.norm(dim=-1, keepdim=True)
        return outputs.tolist()[0]


def image_embeddings_flava(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as e:
        image_path = FrameCache.get_image_path(image_path)
        image = Image.open(image_path).convert("RGB")
    
    # Process image with FLAVA processor
    inputs = _get_flava_processor()(images=image, return_tensors="pt").to(device)
    
    with torch.no_grad():
        # Get image features using FLAVA model
        outputs = _get_flava_model().get_image_features(**inputs)
        # Get the pooled output for global image embedding
        image_embed = outputs.pooler_output
        # Normalize the embeddings
        image_embed = image_embed / image_embed.norm(dim=-1, keepdim=True)
        return image_embed.tolist()[0]


def text_embeddings_flava(text):
    # Process text with FLAVA processor
    inputs = _get_flava_processor()(text=[text], return_tensors="pt", padding=True).to(device)
    
    with torch.no_grad():
        # Get text features using FLAVA model
        outputs = _get_flava_model().get_text_features(**inputs)
        # Get the pooled output for global text embedding
        text_embed = outputs.pooler_output
        # Normalize the embeddings
        text_embed = text_embed / text_embed.norm(dim=-1, keepdim=True)
        return text_embed.tolist()[0]


def embedding_similarity(embedding0, embedding1):
    # TODO maybe find out a way to not have to reconvert back to tensor
    # since this might be less efficient then a simple list
    t0 = torch.Tensor([list(embedding0)])
    t1 = torch.Tensor([list(embedding1)])
    return torch.nn.functional.cosine_similarity(t0, t1)
