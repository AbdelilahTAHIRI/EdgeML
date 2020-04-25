#-*- coding:utf-8 -*-

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import os
import torch
import argparse
import torch.nn as nn
import torch.utils.data as data
import torch.backends.cudnn as cudnn
import torchvision.transforms as transforms

import cv2
import time
import numpy as np
from PIL import Image, ImageFilter

from data.config import cfg
from torch.autograd import Variable
from utils.augmentations import to_chw_bgr

from importlib import import_module



parser = argparse.ArgumentParser(description='face detection demo')
parser.add_argument('--save_dir', type=str, default='results/',
                    help='Directory for detect result')
parser.add_argument('--model', type=str,
                    default='weights/rpool_face_c.pth', help='trained model')
                    #small_fgrnn_smallram_sd.pth', help='trained model')
parser.add_argument('--thresh', default=0.2, type=float,
                    help='Final confidence threshold')
parser.add_argument('--model_arch',
                    default='RPool_Face_C', type=str,
                    choices=['RPool_Face_C', 'RPool_Face_B', 'RPool_Face_A', 'RPool_Face_Quant'],
                    help='choose architecture among rpool variants')
parser.add_argument('--image_folder', default=None, type=str, help='folder containing images')

parser.add_argument('--checkpoint_type', type=str,
                    default='old', 
                    choices=['old','new'],
                    help='specify the type of checkpoint being used : 'old' for the ones provided and 'new' if you trained your own model to test')

args = parser.parse_args()


if not os.path.exists(args.save_dir):
    os.makedirs(args.save_dir)

use_cuda = torch.cuda.is_available()

if use_cuda:
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
else:
    torch.set_default_tensor_type('torch.FloatTensor')


def detect(net, img_path, thresh):
    #img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    img = Image.open(img_path)
    
    #if img.mode == 'L':
    img = img.convert('RGB')

    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    img = np.array(img)
    height, width, _ = img.shape
    max_im_shrink = np.sqrt(
        1700 * 1200 / (img.shape[0] * img.shape[1]))
    image = cv2.resize(img, None, None, fx=max_im_shrink,
                      fy=max_im_shrink, interpolation=cv2.INTER_LINEAR)
    # img = cv2.resize(img, (640, 640))
    x = to_chw_bgr(image)
    x = x.astype('float32')
    x -= cfg.img_mean
    x = x[[2, 1, 0], :, :]

    x = Variable(torch.from_numpy(x).unsqueeze(0))
    if use_cuda:
        x = x.cuda()
    t1 = time.time()
    y = net(x)
    detections = y.data
    scale = torch.Tensor([img.shape[1], img.shape[0],
                          img.shape[1], img.shape[0]])

    img = cv2.imread(img_path, cv2.IMREAD_COLOR)

    for i in range(detections.size(1)):
        j = 0
        while detections[0, i, j, 0] >= thresh:
            score = detections[0, i, j, 0]
            pt = (detections[0, i, j, 1:] * scale).cpu().numpy()
            left_up, right_bottom = (pt[0], pt[1]), (pt[2], pt[3])
            j += 1
            cv2.rectangle(img, left_up, right_bottom, (0, 0, 255), 2)
            conf = "{:.3f}".format(score)
            point = (int(left_up[0]), int(left_up[1] - 5))
            cv2.putText(img, conf, point, cv2.FONT_HERSHEY_COMPLEX,
                       0.6, (0, 255, 0), 1)

    t2 = time.time()
    print('detect:{} timer:{}'.format(img_path, t2 - t1))

    cv2.imwrite(os.path.join(args.save_dir, os.path.basename(img_path)), img)


if __name__ == '__main__':

    module = import_module('models.' + args.model_arch)
    net = module.build_s3fd('test', cfg.NUM_CLASSES)

    checkpoint_dict = torch.load(args.model)

    model_dict = net.state_dict()

    if args.checkpoint_type == 'old':
        checkpoint_dict['rnn_model.cell_rnn.cell.W'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_rnn.cell.W'], 0, 1))
        checkpoint_dict['rnn_model.cell_rnn.cell.U'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_rnn.cell.U'], 0, 1))

        checkpoint_dict['rnn_model.cell_rnn.unrollRNN.RNNCell.W'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_rnn.unrollRNN.RNNCell.W'], 0, 1))
        checkpoint_dict['rnn_model.cell_rnn.unrollRNN.RNNCell.U'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_rnn.unrollRNN.RNNCell.U'], 0, 1))



        checkpoint_dict['rnn_model.cell_bidirrnn.cell.W'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_bidirrnn.cell.W'], 0, 1))
        checkpoint_dict['rnn_model.cell_bidirrnn.cell.U'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_bidirrnn.cell.U'], 0, 1))

        checkpoint_dict['rnn_model.cell_bidirrnn.unrollRNN.RNNCell.W'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_bidirrnn.unrollRNN.RNNCell.W'], 0, 1))
        checkpoint_dict['rnn_model.cell_bidirrnn.unrollRNN.RNNCell.U'] = torch.nn.Parameter(torch.transpose(checkpoint_dict['rnn_model.cell_bidirrnn.unrollRNN.RNNCell.U'], 0, 1))



    model_dict.update(checkpoint_dict) 
    net.load_state_dict(model_dict)



    net.eval()

    # import pdb;pdb.set_trace()

    if use_cuda:
        net.cuda()
        cudnn.benckmark = True

    img_path = args.image_folder
    img_list = [os.path.join(img_path, x)
                for x in os.listdir(img_path) if x.endswith('bmp')]
    for path in img_list:
        detect(net, path, args.thresh)
