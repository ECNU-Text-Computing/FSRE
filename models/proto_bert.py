import sys
sys.path.append('..')
import fewshot_re_kit
import torch
from torch import autograd, optim, nn
from torch.autograd import Variable
from torch.nn import functional as F

class Proto_BERT(fewshot_re_kit.framework.FewShotREModel):
    
    def __init__(self, sentence_encoder, dot=False, relation_encoder=None, N=5, Q=1):
        fewshot_re_kit.framework.FewShotREModel.__init__(self, sentence_encoder)
        # self.fc = nn.Linear(hidden_size, hidden_size)
        self.drop = nn.Dropout()
        self.dot = dot
        
        
        self.relation_encoder = relation_encoder
        self.hidden_size = 768
    
    def __dist__(self, x, y, dim):
        if self.dot:
            return (x * y).sum(dim)
        else:
            return -(torch.pow(x - y, 2)).sum(dim)

    def __batch_dist__(self, S, Q):
        return self.__dist__(S.unsqueeze(1), Q.unsqueeze(2), 3)

    def forward(self, support, query, rel_txt, N, K, total_Q):
        '''
        support: Inputs of the support set.
        query: Inputs of the query set.
        N: Num of classes
        K: Num of instances for each class in the support set
        Q: Num of instances in the query set
        '''
        
        
        
        
        support_h, support_t,  s_loc = self.sentence_encoder(support) # (B * N * K, D), where D is the hidden size
        query_h, query_t,  q_loc = self.sentence_encoder(query) # (B * total_Q, D)

        support = torch.cat((support_h, support_t), -1)
        query = torch.cat((query_h, query_t), -1)
    
        
        support = support.view(-1, N, K, self.hidden_size*2) # (B, N, K, D)
        query = query.view(-1, total_Q, self.hidden_size*2) # (B, total_Q, D)
        

        # Prototypical Networks 
        # Ignore NA policy
        support = torch.mean(support, 2) # Calculate prototype for each class

        
        
        
        logits = self.__batch_dist__(support, query) # (B, total_Q, N)
        minn, _ = logits.min(-1)
        logits = torch.cat([logits, minn.unsqueeze(2) - 1], 2) # (B, total_Q, N + 1)
        _, pred = torch.max(logits.view(-1, N + 1), 1)
        return logits, pred

    
    
    
