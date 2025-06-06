from fewshot_re_kit.data_loader import get_loader, get_loader_pair, get_loader_unsupervised, get_loader_pair2, get_loader2
from fewshot_re_kit.framework import FewShotREFramework
from fewshot_re_kit.sentence_encoder import CNNSentenceEncoder, BERTSentenceEncoder, BERTPAIRSentenceEncoder, RobertaSentenceEncoder, RobertaPAIRSentenceEncoder, BERTRelationEncoder
import models
from models.proto import Proto
from models.proto_bert import Proto_BERT
from models.d import Discriminator
import sys
import torch
from torch import optim, nn
import numpy as np
import json
import argparse
import os
import random
import time


#os.environ["CUDA_VISIBLE_DEVICES"] = '1'
def setup_seed(seed):
	torch.manual_seed(seed)
	if torch.cuda.is_available():
		torch.cuda.manual_seed(seed)
		torch.cuda.manual_seed_all(seed)
	random.seed(seed)
	np.random.seed(seed)
	torch.backends.cudnn.deterministic = True
	torch.backends.cudnn.benchmard = False
	torch.random.manual_seed(seed)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--train', default='train_data_6',
            help='train file')
    parser.add_argument('--val', default='validation_data',
            help='val file')
    parser.add_argument('--test', default='test_data',
            help='test file')
    parser.add_argument('--adv', default=None,
            help='adv file')
    parser.add_argument('--trainN', default=3, type=int,
            help='N in train')
    parser.add_argument('--N', default=3, type=int,
            help='N way')
    parser.add_argument('--K', default=5, type=int,
            help='K shot')
    parser.add_argument('--Q', default=1, type=int,
            help='Num of query per class')
    parser.add_argument('--batch_size', default=1, type=int,
            help='batch size')
    parser.add_argument('--train_iter', default=5000, type=int,
            help='num of iters in training')
    parser.add_argument('--val_iter', default=2000, type=int,
            help='num of iters in validation')
    parser.add_argument('--test_iter', default=2000, type=int,
            help='num of iters in testing')
    parser.add_argument('--val_step', default=1000, type=int,
           help='val after training how many iters')
    parser.add_argument('--model', default='proto_bert',
            help='model name')
    parser.add_argument('--encoder', default='bert',
            help='encoder: cnn or bert or roberta')
    parser.add_argument('--max_length', default=256, type=int,
           help='max length')
    parser.add_argument('--lr', default=-1, type=float,
           help='learning rate')
    parser.add_argument('--weight_decay', default=1e-5, type=float,
           help='weight decay')
    parser.add_argument('--dropout', default=0.0, type=float,
           help='dropout rate')
    parser.add_argument('--na_rate', default=0, type=int,
           help='NA rate (NA = Q * na_rate)')
    parser.add_argument('--grad_iter', default=1, type=int,
           help='accumulate gradient every x iterations')
    parser.add_argument('--optim', default='adamw',
           help='sgd / adam / adamw')
    parser.add_argument('--hidden_size', default=768, type=int,
           help='hidden size')
    parser.add_argument('--load_ckpt', default=None,
           help='load ckpt')
    parser.add_argument('--save_ckpt', default=None,
           help='save ckpt')
    parser.add_argument('--fp16', action='store_true',
           help='use nvidia apex fp16')
    parser.add_argument('--only_test', action='store_true',
           help='only test')
    
    parser.add_argument('--test_online', action='store_true',
           help='generate the result for submitting')
    
    parser.add_argument('--ckpt_name', type=str, default='',
           help='checkpoint name.')

    
    parser.add_argument('--seed', default=42, type=int,
           help='seed')
    
    # only for bert / roberta
    parser.add_argument('--pair', action='store_true',
           help='use pair model')
    parser.add_argument('--pretrain_ckpt', default="bert-base-uncased",
           help='bert / roberta pre-trained checkpoint')
    parser.add_argument('--cat_entity_rep', default=True,
           help='concatenate entity representation as sentence rep')

    # only for prototypical networks
    parser.add_argument('--dot', action='store_true', 
           help='use dot instead of L2 distance for proto')

    # only for mtb
    parser.add_argument('--no_dropout', action='store_true',
           help='do not use dropout after BERT (still has dropout in BERT).')
    
    # experiment
    parser.add_argument('--mask_entity', action='store_true',
           help='mask entity names')
    parser.add_argument('--use_sgd_for_bert', action='store_true',
           help='use SGD instead of AdamW for BERT.')
           
           
    parser.add_argument('--test_output', default=None,
            help='test file')
    
    parser.add_argument('--backend_model', type=str, default='bert',
           help='checkpoint name.')
    
    parser.add_argument('--add_prompt', default=None, type=str,
            help='whether to add prompt information in the front or back, value = front/back/None')

    opt = parser.parse_args()
    trainN = opt.trainN
    N = opt.N
    K = opt.K
    Q = opt.Q
    batch_size = opt.batch_size
    model_name = opt.model
    encoder_name = opt.encoder
    max_length = opt.max_length
    add_prompt = opt.add_prompt

    
    print("{}-way-{}-shot Few-Shot Relation Classification".format(N, K))
    print("training_set: {}".format(opt.train))
    print("model: {}".format(model_name))
    print("encoder: {}".format(encoder_name))
    print("max_length: {}".format(max_length))
    print("learning rate: {}".format(opt.lr))
    print("backend model: {}".format(opt.backend_model))
    print("add_prompt:{}".format(opt.add_prompt))


    setup_seed(opt.seed)
    
    
    if encoder_name == 'cnn':
        try:
            glove_mat = np.load('./pretrain/glove/glove_mat.npy')
            glove_word2id = json.load(open('./pretrain/glove/glove_word2id.json'))
        except:
            raise Exception("Cannot find glove files.")
        sentence_encoder = CNNSentenceEncoder(
                glove_mat,
                glove_word2id,
                max_length)
    elif encoder_name == 'bert':
        pretrain_ckpt = opt.pretrain_ckpt or 'bert-base-uncased'
        
        
        if opt.pair:
            sentence_encoder = BERTPAIRSentenceEncoder(
                    pretrain_ckpt,
                    max_length)
        else:
            sentence_encoder = BERTSentenceEncoder(
                    pretrain_ckpt,
                    max_length,
                    cat_entity_rep=opt.cat_entity_rep,
                    mask_entity=opt.mask_entity,
                    backend_model=opt.backend_model)
            
            
    elif encoder_name == 'roberta':
        pretrain_ckpt = opt.pretrain_ckpt or 'roberta-base'
        if opt.pair:
            sentence_encoder = RobertaPAIRSentenceEncoder(
                    pretrain_ckpt,
                    max_length)
        else:
            sentence_encoder = RobertaSentenceEncoder(
                    pretrain_ckpt,
                    max_length,
                    cat_entity_rep=opt.cat_entity_rep)
    else:
        raise NotImplementedError
     
    
    if opt.pair:
        train_data_loader = get_loader_pair(opt.train, sentence_encoder,
                N=trainN, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size, encoder_name=encoder_name)
        val_data_loader = get_loader_pair(opt.val, sentence_encoder,
                N=N, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size, encoder_name=encoder_name)
        test_data_loader = get_loader_pair(opt.test, sentence_encoder,
                N=N, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size, encoder_name=encoder_name)
    else:
        train_data_loader = get_loader(opt.train, sentence_encoder,
                N=trainN, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size, add_prompt= add_prompt)
        val_data_loader = get_loader(opt.val, sentence_encoder,
                N=N, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size, add_prompt= add_prompt)
        test_data_loader = get_loader2(opt.test, sentence_encoder,
                N=N, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size, add_prompt= add_prompt)
        if opt.adv:
            adv_data_loader = get_loader_unsupervised(opt.adv, sentence_encoder,
                N=trainN, K=K, Q=Q, na_rate=opt.na_rate, batch_size=batch_size)
   
    if opt.optim == 'sgd':
        pytorch_optim = optim.SGD
    elif opt.optim == 'adam':
        pytorch_optim = optim.Adam
    elif opt.optim == 'adamw':
        from transformers import AdamW
        pytorch_optim = AdamW
    else:
        raise NotImplementedError
    if opt.adv:
        d = Discriminator(opt.hidden_size)
        framework = FewShotREFramework(train_data_loader, val_data_loader, test_data_loader, adv_data_loader, adv=opt.adv, d=d)
    else:
        framework = FewShotREFramework(train_data_loader, val_data_loader, test_data_loader)
        
    prefix = '-'.join([model_name, encoder_name, opt.train, opt.val, str(N), str(K)])
    if opt.adv is not None:
        prefix += '-adv_' + opt.adv
    if opt.na_rate != 0:
        prefix += '-na{}'.format(opt.na_rate)
    if opt.dot:
        prefix += '-dot'
    if opt.cat_entity_rep:
        prefix += '-catentity'
    if len(opt.ckpt_name) > 0:
        prefix += '-' + opt.ckpt_name
    
    if model_name == 'proto':
        model = Proto(sentence_encoder, dot=opt.dot, relation_encoder=None)
    elif model_name == 'proto_bert':
        model = Proto_BERT(sentence_encoder, dot=opt.dot, relation_encoder=None)
    else:
        raise NotImplementedError
    
    
    if not os.path.exists('checkpoint'):
        os.mkdir('checkpoint')
    ckpt = 'checkpoint/{}.pth.tar'.format(prefix)
    if opt.save_ckpt:
        ckpt = opt.save_ckpt

    if torch.cuda.is_available():
        model.cuda()
    
    
    if not opt.only_test and (not opt.test_online):
        if encoder_name in ['bert', 'roberta']:
            bert_optim = True
        else:
            bert_optim = False

        if opt.lr == -1:
            if bert_optim:
                opt.lr = 2e-5
            else:
                opt.lr = 1e-1
        
        opt.train_iter = opt.train_iter * opt.grad_iter
        framework.train(model, prefix, batch_size, trainN, N, K, Q,
                pytorch_optim=pytorch_optim, load_ckpt=opt.load_ckpt, save_ckpt=ckpt,
                na_rate=opt.na_rate, val_step=opt.val_step, fp16=opt.fp16, pair=opt.pair, 
                train_iter=opt.train_iter, val_iter=opt.val_iter, bert_optim=bert_optim, 
                learning_rate=opt.lr, use_sgd_for_bert=opt.use_sgd_for_bert, grad_iter=opt.grad_iter)
    
    elif opt.test_online:
        print('this is the test online type.')
        ckpt = opt.load_ckpt
        if ckpt is None:
            print("Warning: --load_ckpt is not specified. Will load Hugginface pre-trained checkpoint.")
            ckpt = 'none'
        framework.eval(model, batch_size, N, K, Q, opt.test_iter, na_rate=opt.na_rate, ckpt=ckpt, pair=opt.pair, test_output=opt.test_output)
    
    else:
        ckpt = opt.load_ckpt
        if ckpt is None:
            print("Warning: --load_ckpt is not specified. Will load Hugginface pre-trained checkpoint.")
            ckpt = 'none'
        acc = framework.eval(model, batch_size, N, K, Q, opt.test_iter, na_rate=opt.na_rate, ckpt=ckpt, pair=opt.pair)
        print("RESULT: %.2f" % (acc * 100))

if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time() 
    print("Total time usage: {:.2f}seconds".format(end_time - start_time))
