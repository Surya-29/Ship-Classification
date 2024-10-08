import os
import argparse
import cv2
import numpy as np
import sys
import glob
import importlib.util

parser = argparse.ArgumentParser()
parser.add_argument(
    '--modeldir', help='Folder the .tflite file is located in', required=True)
parser.add_argument(
    '--graph', help='Name of the .tflite file, if different than detect.tflite', default='detect.tflite')
parser.add_argument(
    '--labels', help='Name of the labelmap file, if different than labelmap.txt', default='labelmap.txt')
parser.add_argument(
    '--threshold', help='Minimum confidence threshold for displaying detected objects', default=0.5)
parser.add_argument(
    '--image', help='Name of the single image to perform detection on. To run detection on multiple images, use --imagedir', default=None)
parser.add_argument(
    '--imagedir', help='Name of the folder containing images to perform detection on. Folder must contain only images.', default=None)
parser.add_argument(
    '--save_results', help='Save labeled images and annotation data to a results folder', action='store_true')
parser.add_argument('--noshow_results',
                    help='Don\'t show result images (only use this if --save_results is enabled)', action='store_false')
parser.add_argument(
    '--edgetpu', help='Use Coral Edge TPU Accelerator to speed up detection', action='store_true')

args = parser.parse_args()

MODEL_NAME = args.modeldir
GRAPH_NAME = args.graph
LABELMAP_NAME = args.labels

min_conf_threshold = float(args.threshold)
use_TPU = args.edgetpu

save_results = args.save_results
show_results = args.noshow_results

IM_NAME = args.image
IM_DIR = args.imagedir

if (IM_NAME and IM_DIR):
    print('Error! Please only use the --image argument or the --imagedir argument, not both. Issue "python TFLite_detection_image.py -h" for help.')
    sys.exit()

if (not IM_NAME and not IM_DIR):
    IM_NAME = 'test1.jpg'

pkg = importlib.util.find_spec('tflite_runtime')
if pkg:
    from tflite_runtime.interpreter import Interpreter
    if use_TPU:
        from tflite_runtime.interpreter import load_delegate
else:
    from tensorflow.lite.python.interpreter import Interpreter
    if use_TPU:
        from tensorflow.lite.python.interpreter import load_delegate

if use_TPU:
    if (GRAPH_NAME == 'detect.tflite'):
        GRAPH_NAME = 'edgetpu.tflite'


CWD_PATH = os.getcwd()
if IM_DIR:
    PATH_TO_IMAGES = os.path.join(CWD_PATH, IM_DIR)
    images = glob.glob(PATH_TO_IMAGES + '/*.jpg') + glob.glob(PATH_TO_IMAGES +'/*.png') + glob.glob(PATH_TO_IMAGES + '/*.bmp')
    if save_results:
        RESULTS_DIR = IM_DIR + '_results'
elif IM_NAME:
    PATH_TO_IMAGES = os.path.join(CWD_PATH, IM_NAME)
    images = glob.glob(PATH_TO_IMAGES)
    if save_results:
        RESULTS_DIR = 'results'
if save_results:
    RESULTS_PATH = os.path.join(CWD_PATH, RESULTS_DIR)
    if not os.path.exists(RESULTS_PATH):
        os.makedirs(RESULTS_PATH)
PATH_TO_CKPT = os.path.join(CWD_PATH, MODEL_NAME, GRAPH_NAME)
PATH_TO_LABELS = os.path.join(CWD_PATH, MODEL_NAME, LABELMAP_NAME)
with open(PATH_TO_LABELS, 'r') as f:
    labels = [line.strip() for line in f.readlines()]
if use_TPU:
    interpreter = Interpreter(model_path=PATH_TO_CKPT,experimental_delegates=[load_delegate('libedgetpu.so.1.0')])
    print(PATH_TO_CKPT)
else:
    interpreter = Interpreter(model_path=PATH_TO_CKPT)

interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
height = input_details[0]['shape'][1]
width = input_details[0]['shape'][2]
floating_model = (input_details[0]['dtype'] == np.float32)
input_mean = 127.5
input_std = 127.5
outname = output_details[0]['name']


for image_path in images:
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    imH, imW, _ = image.shape
    image_resized = cv2.resize(image_rgb, (width, height))
    input_data = np.expand_dims(image_resized, axis=0)
    if floating_model:
        input_data = (np.float32(input_data) - input_mean) / input_std
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    tflite_model_predictions = interpreter.get_tensor(output_details[0]['index'])
    cv2.putText(image, str(labels[np.argmax(tflite_model_predictions)]),(20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    detections=[]
    detections.append(str(labels[np.argmax(tflite_model_predictions)]))
    
    # if show_results:
    #     cv2.imshow('Object detector', image)
    #     if cv2.waitKey(0) == ord('q'):
    #         break

    if save_results:
        image_fn = os.path.basename(image_path)
        image_savepath = os.path.join(CWD_PATH, RESULTS_DIR, image_fn)

        base_fn, ext = os.path.splitext(image_fn)
        txt_result_fn = base_fn + '.txt'
        txt_savepath = os.path.join(CWD_PATH, RESULTS_DIR, txt_result_fn)
        cv2.imwrite(image_savepath, image)
        with open(txt_savepath, 'w') as f:
            for detection in detections:
                f.write(detection)

cv2.destroyAllWindows()
