from PIL import Image
import torch
import clip

from image.frame_cache import FrameCache
from utils.config import config

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load(config.clip_model, device=device)

def image_embeddings(image_path):
    try:
     image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    except Exception as e:
        image_path = FrameCache.get_first_frame(image_path)
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        return model.encode_image(image).tolist()[0]


def text_embeddings(text):
    tokens = clip.tokenize([text]).to(device)
    with torch.no_grad():
        return model.encode_text(tokens).tolist()[0]


def embedding_similarity(embedding0, embedding1):
    # TODO maybe find out a way to not have to reconvert back to tensor
    # since this might be less efficient then a simple list
    t0 = torch.Tensor([list(embedding0)])
    t1 = torch.Tensor([list(embedding1)])
    return torch.nn.functional.cosine_similarity(t0, t1)
