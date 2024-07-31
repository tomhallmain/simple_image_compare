import os

import cv2 
import numpy as np

from utils.utils import Utils

def rotate_image(image_path, right=False):
	try:
		#loading the image into a numpy array 
		img = cv2.imread(image_path)
		#rotating the image
		if right:
			rotated = np.rot90(img, k=-1)
		else:
			rotated = np.rot90(img, k=1)

		current_extension = os.path.splitext(image_path)[-1]
		temp_filepath = os.path.join(os.path.dirname(image_path), 'temp' + current_extension)
		cv2.imwrite(temp_filepath, rotated)
		Utils.move_file(temp_filepath, image_path, overwrite_existing=True)
	except Exception as e:
		print(f'Error in rotate image: {e}')

# rotated_90_clockwise = np.rot90(img) #rotated 90 deg once 
# rotated_180_clockwise = np.rot90(rotated_90_clockwise) 
# rotated_270_clockwise = np.rot90(rotated_180_clockwise) 
 
