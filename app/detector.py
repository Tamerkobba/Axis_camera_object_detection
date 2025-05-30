"""
 * Copyright (C) 2021 Axis Communications AB, Lund, Sweden
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
"""

# Object detector application example
import os
import time
import numpy as np
import cv2
from tf_proto_utils import InferenceClient
from vdo_proto_utils import VideoCaptureClient

# Detector object
# Send images for object detection
class Detector:
    def __init__(self):
        self.debug = None
        self.detection_type = None
        self.inference_client = None
        self.model_path = None
        self.object_list = None
        self.threshold = None

    # Do object detection on image
    def detect(self, image):
        image = np.expand_dims(image, axis=0)
        image = image.astype(np.uint8)
        success, result = self.inference_client.infer({'data': image}, self.model_path)
        if not success:
            return False, [], [], []
        
        boxes   = result["boxes"][0]
        scores  = result["scores"][0]
        classes = result["classes"][0].astype(int)

        # 4) Filter out any detections below your threshold
        mask = scores >= self.threshold
        boxes   = boxes[mask]
        scores  = scores[mask]
        classes = classes[mask]

        # 5) Return in the same format your drawing code expects
        return True, boxes, classes, scores

    # Load object labels from file
    def read_object_list(self, object_list_path):
        self.object_list = {}
        self.detection_type = 'Objects'
        for row in open(object_list_path, 'r'):
            (classID, label) = row.strip().split(" ", maxsplit=1)
            label = label.strip().split(",", maxsplit=1)[0]
            self.object_list[int(classID)] = label

    # Draw bounding boxes on image
    def draw_bounding_boxes(self, image, bounding_boxes, obj_classes, color=(1, 190, 200)):
        height, width = image.shape[:2]
        for bounding_box, obj_class in zip(bounding_boxes, obj_classes):
            cv2.rectangle(image,
                          (int(bounding_box[1] * width), int(bounding_box[0] * height)),
                          (int(bounding_box[3] * width), int(bounding_box[2] * height)),
                          color,
                          2)
            if self.object_list is not None:
                cv2.putText(image,
                            self.object_list[int(obj_class.item())],
                            (int(bounding_box[1] * width), int(bounding_box[0] * height - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            color,
                            2)
                print(self.object_list[int(obj_class.item())])
        return image

    # Read environment variables
    def read_enviroment(self):
        self.grpc_socket = os.environ['INFERENCE_HOST']
        self.threshold = float(os.environ.get('DETECTION_THRESHOLD', 0.5))
        self.inference_client =  InferenceClient(self.grpc_socket)

        self.model_path = os.environ['MODEL_PATH']
        image_path = os.environ.get('IMAGE_PATH')
        object_list_path = os.environ.get('OBJECT_LIST_PATH')
        return image_path, object_list_path

    # Run object detection
    def run(self):
        image_path, object_list_path = self.read_enviroment()
        print(f"object-detector-python connect to: {self.grpc_socket}")
        self.read_object_list(object_list_path)
        if image_path is not None:
            while True:
                self.run_image_source(image_path)
        else:
            self.run_camera_source()

    # Run object detection on video stream
    def run_camera_source(self):
        stream_width, stream_height, stream_framerate = (480, 320, 10)
        capture_client = VideoCaptureClient(socket=self.grpc_socket,
                                            stream_width=stream_width,
                                            stream_height=stream_height,
                                            stream_framerate=stream_framerate)

        while True:
            frame = capture_client.get_frame()
            succeed, bounding_boxes, obj_classes, _ = self.detect(frame)
            if not succeed:
                time.sleep(1)
                continue
            frame = self.draw_bounding_boxes(frame, bounding_boxes, obj_classes)

    # Run object detection on single image
    def run_image_source(self, image_path):
        image = cv2.imread(image_path)
        succeed = False
        while not succeed:
            t0 = time.time()
            succeed, bounding_boxes, obj_classes, _ = self.detect(image)
            t1 = time.time()
            time.sleep(1)
        image = self.draw_bounding_boxes(image, bounding_boxes, obj_classes)
        cv2.imwrite('/output/{}-detector.jpg'.format(self.detection_type), image)
        print(f'Total time for image inference: {1000 * (t1 - t0):.0f} ms')


# Main program
if __name__ == '__main__':
    Detector().run()
