import torch
import matplotlib.pyplot as plt
import numpy as np
import torchvision
import torch.nn.functional as F
import argparse
import matplotlib
matplotlib.use('Agg') # Use Agg backend for headless operation
import wandb

import glob 
from PIL import Image 
import os 
from datetime import datetime
import time
import math
import sys

from model_utils import *
from data_utils import *
from metric_utils import *
from train_evaluate import *

### ARGUMENTS ###

parser = argparse.ArgumentParser(description='Eqprop')

parser.add_argument('--wandb_project', type=str, default='oim-eq-prop', help='WandB project name')
parser.add_argument('--wandb_entity', type=str, default='alexgower-team', help='WandB entity/username')
parser.add_argument('--wandb_name', type=str, default=None, help='WandB run name')
parser.add_argument('--wandb_group', type=str, default=None, help='WandB group name for organizing related runs')
parser.add_argument('--wandb_mode', type=str, default='disabled', help='WandB mode (online/offline/disabled)')

parser.add_argument('--model',type = str, default = 'MLP', metavar = 'm', help='model e.g. MLP, OIM_MLP, CNN') 
parser.add_argument('--act',type = str, default = 'cos', metavar = 'a', help='activation function, their default was mysig')
parser.add_argument('--task',type = str, default = 'MNIST', metavar = 't', help='task')
parser.add_argument('--optim', type = str, default = 'sgd', metavar = 'opt', help='optimizer for training')
parser.add_argument('--loss', type = str, default = 'mse', metavar = 'lss', help='loss for training')
parser.add_argument('--alg', type = str, default = 'EP', metavar = 'al', help='EP or BPTT or CEP') # TODO think about CEP later
parser.add_argument('--thirdphase', default = False, action = 'store_true', help='add third phase for higher order evaluation of the gradient (default: False)')
parser.add_argument('--save', default = False, action = 'store_true', help='saving results')
parser.add_argument('--todo', type = str, default = 'train', metavar = 'tr', help='training or plot gdu curves or evaluate')
parser.add_argument('--load-path', type = str, default = '', metavar = 'l', help='load a model')
parser.add_argument('--seed',type = int, default = None, metavar = 's', help='random seed')
parser.add_argument('--device',type = int, default = 0, metavar = 'd', help='device')

parser.add_argument('--archi', nargs='+', type = int, default = [784, 512, 10], metavar = 'A', help='architecture of the network')
parser.add_argument('--weight_lrs', nargs='+', type = float, default = [], metavar = 'l', help='layer wise lr')
parser.add_argument('--bias_lrs', nargs='+', type = float, default = [], metavar = 'bl', help='layer wise lr for biases (only applies to OIM models)')
parser.add_argument('--sync_lrs', nargs='+', type = float, default = [], metavar = 'sl', help='layer wise lr for sync parameters (only applies to OIM models)')
parser.add_argument('--mbs',type = int, default = 20, metavar = 'M', help='minibatch size')
parser.add_argument('--T1',type = int, default = 20, metavar = 'T1', help='Time of first phase')
parser.add_argument('--T2',type = int, default = 4, metavar = 'T2', help='Time of second phase (and third phase if applicable)')
parser.add_argument('--betas', nargs='+', type = float, default = [0.0, 0.01], metavar = 'Bs', help='Betas in first and second (and third if applicable) phase')
parser.add_argument('--epochs',type = int, default = 1, metavar = 'EPT',help='Number of epochs per tasks')
parser.add_argument('--scale',type = float, default = None, metavar = 'g', help='scal factor for weight init')
parser.add_argument('--epsilon', type=float, default=0.1, help='Step size for OIM dynamics (default=0.1)')
parser.add_argument('--random_phase_initialisation', default=False, action='store_true', help='Initialize phases randomly between 0 and 2π (default: False)')
parser.add_argument('--reinitialise_neurons', default=False, action='store_true', help='Reinitialize neurons before second phase (and third if applicable) (default: False)')
parser.add_argument('--N_data_train', type=int, default=1000, help='Number of training data points (default: 1000)')
parser.add_argument('--N_data_test', type=int, default=100, help='Number of test data points (default: 100)')
parser.add_argument('--input_positive_negative_mapping', default=False, action='store_true', help='Remap input pixel values from [0,1] to [-1,1] (default: False)')
parser.add_argument('--debug', default=False, action='store_true', help='Debug mode (default: False)')
parser.add_argument('--plot', default = False, action = 'store_true', help='Enable plotting of phase dynamics during training and evaluation')

parser.add_argument('--wds', nargs='+', type = float, default = None, metavar = 'l', help='layer weight decays')
parser.add_argument('--lr-decay', default = False, action = 'store_true', help='enabling learning rate decay')
parser.add_argument('--mmt',type = float, default = 0.0, metavar = 'mmt', help='Momentum for sgd')

parser.add_argument('--check-thm', default = False, action = 'store_true', help='checking the gdu while training')
parser.add_argument('--random-sign', default = False, action = 'store_true', help='randomly switch beta_2 sign')
parser.add_argument('--data-aug', default = False, action = 'store_true', help='enabling data augmentation for cifar10')
parser.add_argument('--softmax', default = False, action = 'store_true', help='softmax loss with parameters (default: False)')
parser.add_argument('--cep-debug', default = False, action = 'store_true', help='debug cep')

# parser.add_argument('--pools', type = str, default = 'mm', metavar = 'p', help='pooling') 
# parser.add_argument('--channels', nargs='+', type = int, default = [32, 64], metavar = 'C', help='channels of the convnet')
# parser.add_argument('--kernels', nargs='+', type = int, default = [5, 5], metavar = 'K', help='kernels sizes of the convnet')
# parser.add_argument('--strides', nargs='+', type = int, default = [1, 1], metavar = 'S', help='strides of the convnet')
# parser.add_argument('--paddings', nargs='+', type = int, default = [0, 0], metavar = 'P', help='paddings of the conv layers')
# parser.add_argument('--fc', nargs='+', type = int, default = [10], metavar = 'S', help='linear classifier of the convnet')


args = parser.parse_args()
command_line = ' '.join(sys.argv) # Capture the command line arguments
print('\n')
print(command_line) # Print the command line arguments
print('\n')
print('##################################################################')
print('\nargs\tmbs\tT1\tT2\tepochs\tactivation\tbetas')
print('\t',args.mbs,'\t',args.T1,'\t',args.T2,'\t',args.epochs,'\t',args.act, '\t', args.betas)
print('\n')


# Initialize wandb if not disabled
if args.wandb_mode != 'disabled':
    wandb.init(
        project=args.wandb_project,
        entity=args.wandb_entity,
        name=args.wandb_name,
        group=args.wandb_group,
        config=vars(args),
        mode=args.wandb_mode
    )


### ###









### GENERAL INITIAL SETUP ###

# Set device
device = torch.device('cuda:'+str(args.device) if torch.cuda.is_available() else 'cpu')

# Create results directory
if args.save:
    date = datetime.now().strftime('%Y-%m-%d')
    time = datetime.now().strftime('%H-%M-%S')
    if args.load_path=='':
        path = 'results/'+args.alg+'/'+args.loss+'/'+date+'/'+time+'_gpu'+str(args.device)
    else:
        path = args.load_path
    if not(os.path.exists(path)):
        os.makedirs(path)
else:
    path = ''
args.path = path

# Set default dtype
#if args.alg=='CEP' and args.cep_debug:
#    torch.set_default_dtype(torch.float64)
print('Default dtype :\t', torch.get_default_dtype(), '\n')

# Set seed
if args.seed is not None:
    torch.manual_seed(args.seed)


# Define loss function
# Note need to use reduction='none' to avoid averaging over the batch as individual losses are needed for EP updates in nudged phases
if args.loss=='mse':
    criterion = torch.nn.MSELoss(reduction='none').to(device)
elif args.loss=='cel':
    criterion = torch.nn.CrossEntropyLoss(reduction='none').to(device)
print('loss =', criterion, '\n')

### ###






### GENERATE DATASETS ###

if args.task=='MNIST':
    train_loader, test_loader = generate_mnist(args)

# elif args.task=='CIFAR10':
#     if args.data_aug:
#         transform_train = torchvision.transforms.Compose([torchvision.transforms.RandomHorizontalFlip(0.5),
#                                                           torchvision.transforms.RandomCrop(size=[32,32], padding=4, padding_mode='edge'),
#                                                           torchvision.transforms.ToTensor(), 
#                                                           torchvision.transforms.Normalize(mean=(0.4914, 0.4822, 0.4465), 
#                                                                                            std=(3*0.2023, 3*0.1994, 3*0.2010)) ])   
#     else:
#          transform_train = torchvision.transforms.Compose([torchvision.transforms.ToTensor(), 
#                                                           torchvision.transforms.Normalize(mean=(0.4914, 0.4822, 0.4465), 
#                                                                                            std=(3*0.2023, 3*0.1994, 3*0.2010)) ])   

#     transform_test = torchvision.transforms.Compose([torchvision.transforms.ToTensor(), 
#                                                      torchvision.transforms.Normalize(mean=(0.4914, 0.4822, 0.4465), 
#                                                                                       std=(3*0.2023, 3*0.1994, 3*0.2010)) ]) 

#     cifar10_train_dset = torchvision.datasets.CIFAR10('./cifar10_pytorch', train=True, transform=transform_train, download=True)
#     cifar10_test_dset = torchvision.datasets.CIFAR10('./cifar10_pytorch', train=False, transform=transform_test, download=True)

#     # For Validation set
#     val_index = np.random.randint(10)
#     val_samples = list(range( 5000 * val_index, 5000 * (val_index + 1) ))
    
#     #train_loader = torch.utils.data.DataLoader(cifar10_train_dset, batch_size=mbs, sampler = torch.utils.data.SubsetRandomSampler(val_samples), shuffle=False, num_workers=1)
#     train_loader = torch.utils.data.DataLoader(cifar10_train_dset, batch_size=mbs, shuffle=True, num_workers=1)
#     test_loader = torch.utils.data.DataLoader(cifar10_test_dset, batch_size=200, shuffle=False, num_workers=1)

### ###








### DEFINE MODEL ###

if args.load_path=='': # i.e. if no model is loaded

    if args.model=='OIM_MLP':

        # Define activation function
        if args.act=='tanh':
            activation = torch.tanh
        elif args.act=='cos':
            activation = torch.cos


        model = OIM_MLP(args.archi, epsilon=args.epsilon, random_phase_initialisation=args.random_phase_initialisation, activation=activation, path=args.path)

    elif args.model=='MLP':

        # Define activation function
        if args.act=='mysig':
            activation = my_sigmoid
        elif args.act=='sigmoid':
            activation = torch.sigmoid
        elif args.act=='tanh':
            activation = torch.tanh
        elif args.act=='hard_sigmoid':
            activation = hard_sigmoid
        elif args.act=='my_hard_sig':
            activation = my_hard_sig
        elif args.act=='ctrd_hard_sig':
            activation = ctrd_hard_sig

        model = P_MLP(args.archi, activation=activation, path=args.path)  # P_MLP means MLP defined using primitive function


    # elif args.model.find('CNN')!=-1:

    #     if args.task=='MNIST':
    #         pools = make_pools(args.pools)
    #         channels = [1]+args.channels 
    #         if args.model=='CNN':
    #             model = P_CNN(28, channels, args.kernels, args.strides, args.fc, pools, args.paddings, 
    #                               activation=activation, softmax=args.softmax)


    #     elif args.task=='CIFAR10':    
    #        pools = make_pools(args.pools)
    #        channels = [3]+args.channels
    #        if args.model=='CNN':
    #             model = P_CNN(32, channels, args.kernels, args.strides, args.fc, pools, args.paddings,
    #                           activation=activation, softmax=args.softmax)

        
    #     elif args.task=='imagenet':   #only for gducheck
    #         pools = make_pools(args.pools)
    #         channels = [3]+args.channels 
    #         model = P_CNN(224, channels, args.kernels, args.strides, args.fc, pools, args.paddings, 
    #                         activation=activation, softmax=args.softmax)
                       
    #     print('\n')
    #     print('Poolings =', model.pools)



    # Do weight initialization scaling if specified
    if args.scale is not None:
        model.apply(my_init(args.scale))



else: # i.e. if a model is loaded

    model = torch.load(args.load_path + '/model.pt', map_location=device)

model.to(device)
print(model)

### ###











### TRAINING / EVALUATION / GDU CHECK ###


### TRAINING ###

if args.todo=='train':
    assert(len(args.weight_lrs)==len(model.synapses))



    ## Constructing the Optimizer ##
    optim_params = []


    # if (args.alg=='CEP' and args.wds) and not(args.cep_debug):
    #     for idx in range(len(model.synapses)):
    #         args.wds[idx] = (1 - (1 - args.wds[idx] * 0.1 )**(1/args.T2))/args.weight_lrs[idx]

    for idx in range(len(model.synapses)):
        if args.wds is None:
            optim_params.append(  {'params': model.synapses[idx].parameters(), 'lr': args.weight_lrs[idx]}  )
        else:
            optim_params.append(  {'params': model.synapses[idx].parameters(), 'lr': args.weight_lrs[idx], 'weight_decay': args.wds[idx]}  ) # Note weight and biases for same layer get same weight decay

            
    # Add bias and sync parameters to the optimizer (for OIM_MLP model)
    if args.model == 'OIM_MLP':
        # Add bias parameters with custom learning rates if provided
        for idx, bias in enumerate(model.biases):
            lr = args.bias_lrs[idx] 
            if args.wds is None:
                optim_params.append({'params': [bias], 'lr': lr})
            else:
                optim_params.append({'params': [bias], 'lr': lr, 'weight_decay': args.wds[idx]})

        
        # Add sync parameters with custom learning rates if provided
        for idx, sync in enumerate(model.syncs):
            lr = args.sync_lrs[idx]
            if args.wds is None:
                optim_params.append({'params': [sync], 'lr': lr})
            else:
                optim_params.append({'params': [sync], 'lr': lr, 'weight_decay': args.wds[idx]})


    if args.optim=='sgd':
        optimizer = torch.optim.SGD( optim_params, momentum=args.mmt )
    elif args.optim=='adam':
        optimizer = torch.optim.Adam( optim_params )

    ## ##

    ## Constructing the Scheduler ##
    if args.lr_decay:
        #scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer, milestones=[40,80,120], gamma=0.1)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 100, eta_min=1e-5)
    else:
        scheduler = None
    ## ##

    ## Loading the State ##
    if args.load_path!='': # i.e. if a model is loaded
        checkpoint = torch.load(args.load_path + '/checkpoint.tar')
        optimizer.load_state_dict(checkpoint['opt'])
        if checkpoint['scheduler'] is not None and args.lr_decay:
            scheduler.load_state_dict(checkpoint['scheduler'])
    else: 
        checkpoint = None
    
    ## ##

    ## Printing and Saving Hyperparameters ##
    print(optimizer)
    print('\ntraining algorithm : ',args.alg, '\n')
    if args.save and args.load_path=='':
        createHyperparametersFile(path, args, model, command_line)
    ## ##

    ## Training ##
    train(model, optimizer, train_loader, test_loader, args, device, criterion, checkpoint=checkpoint, scheduler=scheduler)
    ## ##   


### ###







### GDU CHECK ###

elif args.todo=='gducheck':

    ## Printing and Saving Hyperparameters ##
    print('\ntraining algorithm : ',args.alg, '\n')
    if args.save and args.load_path=='':
        createHyperparametersFile(path, args, model, command_line)
    ## ##


    if args.task != 'imagenet':
        dataiter = iter(train_loader)
        images, labels = next(dataiter)
        images, labels = images[0:20,:], labels[0:20] # Only using 20 samples for gducheck for visualisation purposes
        images, labels = images.to(device), labels.to(device)

    # else:
    #     images = []
    #     all_files = glob.glob('imagenet_samples/*.JPEG')
    #     for idx, filename in enumerate(all_files):
    #         if idx>2:
    #             break
    #         image = Image.open(filename)
    #         image = torchvision.transforms.functional.center_crop(image, 224)
    #         image = torchvision.transforms.functional.to_tensor(image)
    #         image.unsqueeze_(0)
    #         image = image.add_(-image.mean()).div_(image.std())
    #         images.append(image)
    #     labels = torch.randint(1000, (len(images),))
    #     images = torch.cat(images, dim=0)
    #     images, labels = images.to(device), labels.to(device)
    #     print(images.shape)


    ## GDU Check ##
    beta_1, beta_2 = args.betas
    BPTT, EP = check_gdu(model, images, labels, args, criterion, betas=(beta_1, beta_2))
    if args.thirdphase:
        _, EP_2 = check_gdu(model, images, labels, args, criterion, betas=(beta_1, -beta_2))
    

    RMSE(BPTT, EP) # Print RMSE and sign error between EP and BPTT

    if args.save:
        
        bptt_est = get_estimate(BPTT) 
        ep_est = get_estimate(EP)
        torch.save(bptt_est, path+'/bptt.tar')
        torch.save(BPTT, path+'/BPTT.tar')
        torch.save(ep_est, path+'/ep.tar') 
        torch.save(EP, path+'/EP.tar') 

        if args.thirdphase:
            ep_2_est = get_estimate(EP_2)
            torch.save(ep_2_est, path+'/ep_2.tar')
            torch.save(EP_2, path+'/EP_2.tar')
        
            compare_estimate(bptt_est, ep_est, ep_2_est, path)
        
            plot_gdu(BPTT, EP, path, EP_2=EP_2, alg=args.alg)
        else:
            plot_gdu(BPTT, EP, path, alg=args.alg)

    ## ##

### ###









### EVALUATE ###

elif args.todo=='evaluate':

    training_correct, training_loss, _ = evaluate(model, train_loader, args.T1, device, plot=args.plot, criterion=criterion)
    training_acc = training_correct / len(train_loader.dataset)
    print('\nTrain accuracy :', round(training_acc,2), file=open(path+'/hyperparameters.txt', 'a'))
    print('\nTrain loss :', round(training_loss,4), file=open(path+'/hyperparameters.txt', 'a'))
    
    test_correct, test_loss, _ = evaluate(model, test_loader, args.T1, device, plot=args.plot, criterion=criterion)
    test_acc = test_correct / len(test_loader.dataset)
    print('\nTest accuracy :', round(test_acc, 2), file=open(path+'/hyperparameters.txt', 'a'))
    print('\nTest loss :', round(test_loss,4), file=open(path+'/hyperparameters.txt', 'a'))

### ###








