import cv2 
import numpy as np
 
#loading the image into a numpy array 
img = cv2.imread('<image path>') 
 
#rotating the image 
rotated_90_clockwise = np.rot90(img) #rotated 90 deg once 
rotated_180_clockwise = np.rot90(rotated_90_clockwise) 
rotated_270_clockwise = np.rot90(rotated_180_clockwise) 
 
#displaying all the images in different windows(optional) 
cv2.imshow('Original', img) 
cv2.imshow('90 deg', rotated_90_clockwise) 
cv2.imshow('Inverted', rotated_180_clockwise) 
cv2.imshow('270 deg', rotated_270_clockwise) 
 
k = cv2.waitKey(0) 
if (k == 27): #closes all windows if ESC is pressed 
	cv2.destroyAllWindows() 