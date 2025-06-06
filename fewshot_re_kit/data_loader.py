import torch
import torch.utils.data as data
import os
import numpy as np
import random
import json
import sys
import time
import copy

class FewRelDataset(data.Dataset):
    """
    FewRel Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root, add_prompt):
        self.root = root
        path = os.path.join(root, name + ".json") # json file path
        
        # pid2name = "pid2name"
        # change the name of the pid2name file for different datasets
        pid2name = 'pid2name_i2b2'
        pid2name_path = os.path.join(root, pid2name + ".json")
        
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert(0)
        self.json_data = json.load(open(path))
        self.pid2name = json.load(open(pid2name_path))
        self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder
        self.add_prompt = add_prompt

    def __getraw__(self, item, add_prompt):
        # Add prompt to the sentence
        prompt_sentence = "The relation between them is"
        prompt_list = prompt_sentence.split()
        if add_prompt == "front":
            prompt_list.extend(item['tokens'])
            word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(prompt_list,item['h'][2][0],item['t'][2][0])
        elif add_prompt == "back":
            original_sentence_list = copy.deepcopy(item['tokens'])
            original_sentence_list.extend(prompt_list)
            word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(original_sentence_list,item['h'][2][0],item['t'][2][0])
        else:
            word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(item['tokens'],item['h'][2][0],item['t'][2][0])
        return word, pos1, pos2, mask, lens, pos1_end, pos2_end

    def __additem__(self, d, word, pos1, pos2, mask, lens, pos1_end, pos2_end):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)
        d['lens'].append(lens)
        d['pos1_end'].append(pos1_end)
        d['pos2_end'].append(pos2_end)
        
    
    def __getrel__(self, item):
        word, mask = self.encoder.tokenize_rel(item)
        return word, mask

    def __getname__(self, name):
        word, mask = self.encoder.tokenize_name(name)
        return word, mask
    
    
    def __getitem__(self, index):
        target_classes = random.sample(self.classes, self.N)
        relation_set = {'word': [], 'mask': []}
        support_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens':[], 'pos1_end':[], 'pos2_end': [] }
        query_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens':[], 'pos1_end': [], 'pos2_end': [] }
        query_label = []
        Q_na = int(self.na_rate * self.Q)
        na_classes = list(filter(lambda x: x not in target_classes,  
            self.classes))

        for i, class_name in enumerate(target_classes):
        
            #TODO
            rel_text, rel_text_mask = self.__getrel__(self.pid2name[class_name])
            rel_text, rel_text_mask = torch.tensor(rel_text).long(), torch.tensor(rel_text_mask).long()

            relation_set['word'].append(rel_text)
            relation_set['mask'].append(rel_text_mask)
        
        
            indices = np.random.choice(
                    list(range(len(self.json_data[class_name]))), 
                    self.K + self.Q, False)

            count = 0
            for j in indices:
                word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.__getraw__(
                        self.json_data[class_name][j], self.add_prompt)
                word = torch.tensor(word).long()
                pos1 = torch.tensor(pos1).long()
                pos2 = torch.tensor(pos2).long()
                mask = torch.tensor(mask).long()
                lens = torch.tensor(lens).long()
                pos1_end = torch.tensor(pos1_end).long()
                pos2_end = torch.tensor(pos2_end).long()
                if count < self.K:
                    self.__additem__(support_set, word, pos1, pos2, mask, lens, pos1_end, pos2_end)
                else:
                    self.__additem__(query_set, word, pos1, pos2, mask, lens, pos1_end, pos2_end)
                count += 1

            query_label += [i] * self.Q

        # NA
        for j in range(Q_na):
            cur_class = np.random.choice(na_classes, 1, False)[0]
            index = np.random.choice(
                    list(range(len(self.json_data[cur_class]))),
                    1, False)[0]
            word, pos1, pos2, mask, pos1_end, pos2_end = self.__getraw__(
                    self.json_data[cur_class][index])
            word = torch.tensor(word).long()
            pos1 = torch.tensor(pos1).long()
            pos2 = torch.tensor(pos2).long()
            mask = torch.tensor(mask).long()
            pos1_end = torch.tensor(pos1_end).long()
            pos2_end = torch.tensor(pos2_end).long()
            self.__additem__(query_set, word, pos1, pos2, mask, pos1_end, pos2_end)
        # NA
        
        query_label += [self.N] * Q_na
        return support_set, query_set, query_label, relation_set  #separate support and query -- no pair
    
    def __len__(self):
        return 1000000000

def collate_fn(data):
    batch_support = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens': [], 'pos1_end':[], 'pos2_end': [] }
    batch_query = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens': [], 'pos1_end': [], 'pos2_end': [] }
    batch_relation = {'word': [], 'mask': []}
    batch_label = []
    support_sets, query_sets, query_labels, relation_sets = zip(*data)
    for i in range(len(support_sets)):
        for k in support_sets[i]:
            batch_support[k] += support_sets[i][k]
        for k in query_sets[i]:
            batch_query[k] += query_sets[i][k]
        #TODO
        for k in relation_sets[i]:
            batch_relation[k] += relation_sets[i][k]
        #TODO
        batch_label += query_labels[i]
    
    for k in batch_support:
        batch_support[k] = torch.stack(batch_support[k], 0)
    for k in batch_query:
        batch_query[k] = torch.stack(batch_query[k], 0)
    #TODO
    for k in batch_relation:
        batch_relation[k] = torch.stack(batch_relation[k], 0)
    #TODO
    batch_label = torch.tensor(batch_label)
    return batch_support, batch_query, batch_label, batch_relation

def get_loader(name, encoder, N, K, Q, batch_size, 
        collate_fn=collate_fn, na_rate=0, root='./data', add_prompt = None):
    dataset = FewRelDataset(name, encoder, N, K, Q, na_rate, root, add_prompt)
    ##TODO
    #import pdb
    #pdb.set_trace()
    
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            collate_fn=collate_fn)

    return iter(data_loader)




class FewRelDatasetPair(data.Dataset):
    """
    FewRel Pair Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root, encoder_name):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            print(path)
            print(root)
            print(name)
            assert(0)
        self.json_data = json.load(open(path))
        self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder
        self.encoder_name = encoder_name
        self.max_length = encoder.max_length

    def __getraw__(self, item):
        word = self.encoder.tokenize(item['tokens'],
            item['h'][2][0],
            item['t'][2][0])
        return word 

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __getitem__(self, index):
        target_classes = random.sample(self.classes, self.N)
        support = []
        query = []
        fusion_set = {'word': [], 'mask': [], 'seg': []}
        query_label = []
        Q_na = int(self.na_rate * self.Q)
        na_classes = list(filter(lambda x: x not in target_classes,  
            self.classes))
        #5
        for i, class_name in enumerate(target_classes):
            indices = np.random.choice(
                    list(range(len(self.json_data[class_name]))), 
                    self.K + self.Q, False) ##generate random number from [0, #class_number]  K: support instances   Q: query instances 1
            count = 0
            for j in indices:
                word  = self.__getraw__(
                        self.json_data[class_name][j])
                if count < self.K:
                    support.append(word)
                else:
                    query.append(word)
                count += 1
        
            query_label += [i] * self.Q
        
        #two list: 'support' 'query' contain the support word and the query word
        
        ##TODO
        #import pdb
        #pdb.set_trace()
        
        #*****# when Q_na = 0, next code is not implemented.
        # NA
        for j in range(Q_na):
            cur_class = np.random.choice(na_classes, 1, False)[0]
            index = np.random.choice(
                    list(range(len(self.json_data[cur_class]))),
                    1, False)[0]
            word = self.__getraw__(
                    self.json_data[cur_class][index])
            query.append(word)
        query_label += [self.N] * Q_na
        #*****# when Q_na = 0, above code is not implemented.
        
        for word_query in query:
            for word_support in support:
                if self.encoder_name == 'bert':
                    SEP = self.encoder.tokenizer.convert_tokens_to_ids(['[SEP]'])
                    CLS = self.encoder.tokenizer.convert_tokens_to_ids(['[CLS]'])
                    word_tensor = torch.zeros((self.max_length)).long()
                else:
                    SEP = self.encoder.tokenizer.convert_tokens_to_ids(['</s>'])     
                    CLS = self.encoder.tokenizer.convert_tokens_to_ids(['<s>'])
                    word_tensor = torch.ones((self.max_length)).long()
                new_word = CLS + word_support + SEP + word_query + SEP
                for i in range(min(self.max_length, len(new_word))):
                    word_tensor[i] = new_word[i]
                mask_tensor = torch.zeros((self.max_length)).long()
                mask_tensor[:min(self.max_length, len(new_word))] = 1
                seg_tensor = torch.ones((self.max_length)).long()
                seg_tensor[:min(self.max_length, len(word_support) + 1)] = 0
                fusion_set['word'].append(word_tensor)
                fusion_set['mask'].append(mask_tensor)
                fusion_set['seg'].append(seg_tensor)

        return fusion_set, query_label
    
    def __len__(self):
        return 1000000000

def collate_fn_pair(data):
    batch_set = {'word': [], 'seg': [], 'mask': []}
    batch_label = []
    fusion_sets, query_labels = zip(*data)
    for i in range(len(fusion_sets)):
        for k in fusion_sets[i]:
            batch_set[k] += fusion_sets[i][k]
        batch_label += query_labels[i]
    for k in batch_set:
        batch_set[k] = torch.stack(batch_set[k], 0)
    batch_label = torch.tensor(batch_label)
    return batch_set, batch_label


def collate_fn_pair2(data):
    batch_set = {'word': [], 'seg': [], 'mask': []}
    #batch_label = []
    fusion_sets = data#zip(*data)
    for i in range(len(fusion_sets)):
        for k in fusion_sets[i]:
            batch_set[k] += fusion_sets[i][k]
        #batch_label += query_labels[i]
    for k in batch_set:
        batch_set[k] = torch.stack(batch_set[k], 0)
    #batch_label = torch.tensor(batch_label)
    return batch_set#, batch_label

def get_loader_pair(name, encoder, N, K, Q, batch_size, 
        collate_fn=collate_fn_pair, na_rate=0, root='./data', encoder_name='bert'):
    dataset = FewRelDatasetPair(name, encoder, N, K, Q, na_rate, root, encoder_name)
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            collate_fn=collate_fn)
    return iter(data_loader)

class FewRelUnsupervisedDataset(data.Dataset):
    """
    FewRel Unsupervised Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert(0)
        self.json_data = json.load(open(path))
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder

    def __getraw__(self, item):
        word, pos1, pos2, mask = self.encoder.tokenize(item['tokens'],
            item['h'][2][0],
            item['t'][2][0])
        return word, pos1, pos2, mask 

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __getitem__(self, index):
        total = self.N * self.K
        support_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [] }

        indices = np.random.choice(list(range(len(self.json_data))), total, False)
        for j in indices:
            word, pos1, pos2, mask = self.__getraw__(
                    self.json_data[j])
            word = torch.tensor(word).long()
            pos1 = torch.tensor(pos1).long()
            pos2 = torch.tensor(pos2).long()
            mask = torch.tensor(mask).long()
            self.__additem__(support_set, word, pos1, pos2, mask)

        return support_set
    
    def __len__(self):
        return 1000000000

def collate_fn_unsupervised(data):
    batch_support = {'word': [], 'pos1': [], 'pos2': [], 'mask': []}
    support_sets = data
    for i in range(len(support_sets)):
        for k in support_sets[i]:
            batch_support[k] += support_sets[i][k]
    for k in batch_support:
        batch_support[k] = torch.stack(batch_support[k], 0)
    return batch_support

def get_loader_unsupervised(name, encoder, N, K, Q, batch_size, 
        num_workers=8, collate_fn=collate_fn_unsupervised, na_rate=0, root='./data'):
    dataset = FewRelUnsupervisedDataset(name, encoder, N, K, Q, na_rate, root)
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            num_workers=num_workers,
            collate_fn=collate_fn)
    return iter(data_loader)




##TODO data loader for submitting the test files

class FewRelTestPair(data.Dataset):
    """
    FewRel Pair Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root, encoder_name):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            print(path)
            print(root)
            print(name)
            assert(0)
        self.json_data = json.load(open(path)) ##list type
        #self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder
        self.encoder_name = encoder_name
        self.max_length = encoder.max_length

    def __getraw__(self, item):
        word = self.encoder.tokenize(item['tokens'],
            item['h'][2][0],
            item['t'][2][0])
        return word 

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __getitem__(self, index):
        #target_classes = random.sample(self.classes, self.N)
        support = []
        query = []
        fusion_set = {'word': [], 'mask': [], 'seg': []}
        query_label = []
        Q_na = int(self.na_rate * self.Q)
        #na_classes = list(filter(lambda x: x not in target_classes,  
        #    self.classes))
        ##
        
        #import pdb
        #pdb.set_trace()
        
        count = 0
        data = self.json_data[index]
        #for i in range(index, index + self.N):
        #support
        #data = self.json_data[i]
        support_set = data['meta_train']
        for j in support_set:
            word = self.__getraw__(j[0])
            support.append(word)
              
            query_set = data['meta_test']
            word = self.__getraw__(query_set)
            query.append(word)
        
       
        
        for word_query in query:
            for word_support in support:
                if self.encoder_name == 'bert':
                    SEP = self.encoder.tokenizer.convert_tokens_to_ids(['[SEP]'])
                    CLS = self.encoder.tokenizer.convert_tokens_to_ids(['[CLS]'])
                    word_tensor = torch.zeros((self.max_length)).long()
                else:
                    SEP = self.encoder.tokenizer.convert_tokens_to_ids(['</s>'])     
                    CLS = self.encoder.tokenizer.convert_tokens_to_ids(['<s>'])
                    word_tensor = torch.ones((self.max_length)).long()
                new_word = CLS + word_support + SEP + word_query + SEP
                for i in range(min(self.max_length, len(new_word))):
                    word_tensor[i] = new_word[i]
                mask_tensor = torch.zeros((self.max_length)).long()
                mask_tensor[:min(self.max_length, len(new_word))] = 1
                seg_tensor = torch.ones((self.max_length)).long()
                seg_tensor[:min(self.max_length, len(word_support) + 1)] = 0
                fusion_set['word'].append(word_tensor)
                fusion_set['mask'].append(mask_tensor)
                fusion_set['seg'].append(seg_tensor)

        return fusion_set#, query_label
    
    def __len__(self):
        return 1000000000


def get_loader_pair2(name, encoder, N, K, Q, batch_size, 
        collate_fn=collate_fn_pair2, na_rate=0, root='./data', encoder_name='bert'):
    dataset = FewRelTestPair(name, encoder, N, K, Q, na_rate, root, encoder_name)
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            collate_fn=collate_fn)
    return iter(data_loader)

##
class FewRelTestDataset(data.Dataset):
    """
    FewRel Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root, add_prompt):
        self.root = root
        path = os.path.join(root, name + ".json") # json file path
        
        # pid2name = 'pid2name'
        pid2name = 'pid2name_i2b2.json'
        pid2name_path = os.path.join(root, pid2name + ".json")
        
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert(0)
        self.json_data = json.load(open(path))
        self.pid2name = json.load(open(pid2name_path))
        self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder
        self.add_prompt = add_prompt

    def __getraw__(self, item, add_prompt):
        # word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(item['tokens'],
        #     item['h'][2][0],
        #     item['t'][2][0])
        prompt_sentence = "The relation between them is"
        prompt_list = prompt_sentence.split()
        if add_prompt == "front":
            prompt_list.extend(item['tokens'])
            word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(prompt_list,item['h'][2][0],item['t'][2][0])
        elif add_prompt == "back":
            original_sentence_list = item['tokens']
            original_sentence_list.extend(prompt_list)
            word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(original_sentence_list,item['h'][2][0],item['t'][2][0])
        else:
            word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.encoder.tokenize(item['tokens'],item['h'][2][0],item['t'][2][0])
        return word, pos1, pos2, mask, lens, pos1_end, pos2_end

    def __additem__(self, d, word, pos1, pos2, mask, lens, pos1_end, pos2_end):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)
        d['lens'].append(lens)
        d['pos1_end'].append(pos1_end)
        d['pos2_end'].append(pos2_end)
        
    
    def __getrel__(self, item):
        word, mask = self.encoder.tokenize_rel(item)
        return word, mask

    def __getname__(self, name):
        word, mask = self.encoder.tokenize_name(name)
        return word, mask
    
    
    
    def __getitem__(self, index):
        # This method generates a single episode for few-shot learning:
        # 1. Creates empty dictionaries to store relation info, support set and query set
        # 2. Loads test data from json files and converts to list format
        # 3. For query set:
        #    - Takes one sample from test_list at given index
        #    - Processes the text by adding prompts if specified
        #    - Converts to tensors and adds to query_set
        # 4. For support set:
        #    - First adds K samples from same class as query (excluding query sample)
        #    - Then adds K samples each from N-1 other randomly selected classes
        #    - For each class, also processes its relation text into tensors
        #    - Processes all support samples similar to query
        # 5. Returns:
        #    - support_set: K*N processed support samples
        #    - query_set: Single processed query sample  
        #    - query_label: Label indicating query belongs to first class [0]
        #    - relation_set: Processed relation text for all N classes
        relation_set = {'word': [], 'mask': []}
        support_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens':[], 'pos1_end':[], 'pos2_end': [] }
        query_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens':[], 'pos1_end': [], 'pos2_end': [] }

        # The code is divided into two parts: first determine the query set, then determine the support set. 
        # It is important to remove the index of the query set in the original list before selecting the support set.

        test_list = []
        for i in self.json_data.keys():
            for j in self.json_data[i]:
                test_list.append([i, j])
        with open("./data/test_data_2000.json", 'r') as f:    # We use 2000 samples for testing
            test_data_all = json.load(f)
        # test_list_all = []
        # for i in test_data_all.keys():
        #     for j in test_data_all[i]:
        #         test_list_all.append([i, j])
        # random.shuffle(test_list)
        # random.shuffle(test_list_all)
        # Part 1: query set
        query_key, query_value= test_list[index][0], test_list[index][1]
        word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.__getraw__(query_value, self.add_prompt)
        word = torch.tensor(word).long()
        pos1 = torch.tensor(pos1).long()
        pos2 = torch.tensor(pos2).long()
        mask = torch.tensor(mask).long()
        lens = torch.tensor(lens).long()
        pos1_end = torch.tensor(pos1_end).long()
        pos2_end = torch.tensor(pos2_end).long()
        self.__additem__(query_set, word, pos1, pos2, mask, lens, pos1_end, pos2_end)

        # Part 2: support set
        # First, add samples from the same class as the query
        samples = dict()
        count = 0
        samples[query_key] = []
        while count < self.K:
            sample_key = query_key
            sample_value = random.choice(test_data_all[query_key])
            if sample_value != query_value:
                samples[sample_key].append(sample_value)
                count += 1
        # Then, add samples from N-1 other randomly selected classes
        # Get all keys except the given key
        other_keys = [key for key in test_data_all.keys() if key != query_key]
        # Randomly select N-1 classes
        other_samples = random.sample(other_keys, self.N - 1)
        for key in other_samples:
            samples[key] = []
            for i in range(self.K):
                samples[key].append(random.choice(test_data_all[key]))
        query_label = [0]  
        for key in samples.keys():
            rel_text, rel_text_mask = self.__getrel__(self.pid2name[key])
            rel_text, rel_text_mask = torch.tensor(rel_text).long(), torch.tensor(rel_text_mask).long()
            relation_set['word'].append(rel_text)
            relation_set['mask'].append(rel_text_mask)
            for value in samples[key]:
                word, pos1, pos2, mask, lens, pos1_end, pos2_end = self.__getraw__(value, self.add_prompt)
                word = torch.tensor(word).long()
                pos1 = torch.tensor(pos1).long()
                pos2 = torch.tensor(pos2).long()
                mask = torch.tensor(mask).long()
                lens = torch.tensor(lens).long()
                pos1_end = torch.tensor(pos1_end).long()
                pos2_end = torch.tensor(pos2_end).long()
                self.__additem__(support_set, word, pos1, pos2, mask, lens, pos1_end, pos2_end)
        return support_set, query_set, query_label, relation_set
    
    def __len__(self):
        return 1000000000


def collate_fn22(data):
    batch_support = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens': [], 'pos1_end':[], 'pos2_end': [] }
    batch_query = {'word': [], 'pos1': [], 'pos2': [], 'mask': [], 'lens': [], 'pos1_end': [], 'pos2_end': [] }
    batch_relation = {'word': [], 'mask': []}
    batch_label = []
    support_sets, query_sets, relation_sets = zip(*data)
    for i in range(len(support_sets)):
        for k in support_sets[i]:
            batch_support[k] += support_sets[i][k]
        for k in query_sets[i]:
            batch_query[k] += query_sets[i][k]
        #TODO
        for k in relation_sets[i]:
            batch_relation[k] += relation_sets[i][k]
        #TODO
        #batch_label += query_labels[i]
    
    for k in batch_support:
        batch_support[k] = torch.stack(batch_support[k], 0)
    for k in batch_query:
        batch_query[k] = torch.stack(batch_query[k], 0)
    #TODO
    for k in batch_relation:
        batch_relation[k] = torch.stack(batch_relation[k], 0)
    #TODO
    #batch_label = torch.tensor(batch_label)
    return batch_support, batch_query, batch_relation

def get_loader2(name, encoder, N, K, Q, batch_size, 
         collate_fn=collate_fn, na_rate=0, root='./data', add_prompt = None):
    dataset = FewRelTestDataset(name, encoder, N, K, Q, na_rate, root, add_prompt)
    ##TODO
    #import pdb
    #pdb.set_trace()
    
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            collate_fn=collate_fn)
    return iter(data_loader)