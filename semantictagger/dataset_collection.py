import pdb
from typing import List , Dict

from pandas.core.frame import DataFrame

from semantictagger.paradigms import Encoder

from .dataset import Dataset
from .conllu import CoNLL_U
from .datatypes import Annotation
import matplotlib.pyplot as plt
class DatasetCollection:
    def __init__(self , train :Dataset, dev : Dataset, test: Dataset):
        self.datasets : Dict[Dataset] = {"train" : train , "test" : test , "dev" : dev}

    

    def syntactic_tag_distribution_for_roles(self):
        roles = {}

        i : CoNLL_U = None
        ann : Annotation = None

        for k in self.datasets.values():
            for i in k.entries:
                ann = i.get_srl_annotation()
                dep = i.get_by_tag("deprel")
                
                for i1 , v1 in enumerate(ann):
                    for i2 , v2 in enumerate(v1):
                        if v2 != "_":
                            tag = v2 
                            deptag = dep[i2]
                            if tag in roles:
                                if deptag in roles[tag]['dist']:
                                    roles[tag]['dist'][deptag] += 1
                                else :
                                    roles[tag]['dist'][deptag] = 1
                                roles[tag]['freq'] += 1
                            else :
                                roles[tag] = {"freq":1 , "dist":{}}
                                roles[tag]['dist'][deptag] = 1
            
        
        roles = sorted(roles.items(),key = lambda x : x[1]['freq'] , reverse=True)
        
        for j in roles:
            sortedroles = sorted(list(j[1]['dist'].items()),key = lambda x : x[1] , reverse=True)
            acc = 0 
            for i in sortedroles:
                acc += i[1]
            print(j[0] , j[1]['freq'] , end = "&")
            for i in range(0,min(3,len(sortedroles)-1)):
                print(sortedroles[i][0] , "{:.1f}".format(sortedroles[i][1]/acc*100) , end= "&")
            lastindex = min(3,len(sortedroles))-1
            print(sortedroles[lastindex][0] , "{:.1f}".format(sortedroles[lastindex][1]/acc*100) , end= "\\\\\n")
            print("\\hline")

    def get_by_depth(self):
        depths = [0] * 40 
        for i in self.datasets.items():
            dataset = i[1]
            entry:CoNLL_U = None
            for entry in dataset:
                if entry is None:break
                depths[entry.depth] +=1
        
        print(DataFrame(depths[1:21] , index = range(1,21)).to_latex())

        




    def dist_upos_tag_for_predicates(self):

        uposdistribution = {}

        for i in self.datasets.items():
            
            dataset = i[1]
            entry:CoNLL_U = None

            for entry in dataset:
                upos = entry.get_by_tag("upos")
                frames_indices = entry.get_verb_indices()
                for j in frames_indices:
                    if upos[j] in uposdistribution :
                        uposdistribution[upos[j]] += 1
                    else :
                        uposdistribution[upos[j]] = 1
        
        acc = 0 
        for i in uposdistribution.items():
            acc += i[1]

        mod = 0 
        for i in uposdistribution.items():
            if mod < 3 :
                print(i[0] , "{:.1f}".format(i[1]/acc*100) , end="&")
            else :
                print(i[0] , "{:.1f}".format(i[1]/acc*100) , end="\\\\\n")
            
            mod = (mod + 1) % 4


    def dist_xpos_tag_for_predicates(self):

        xposdistribution = {}

        for i in self.datasets.items():
            
            dataset = i[1]
            entry:CoNLL_U = None

            for entry in dataset:
                upos = entry.get_by_tag("xpos")
                frames_indices = entry.get_verb_indices()
                for j in frames_indices:
                    if upos[j] in xposdistribution :
                        xposdistribution[upos[j]] += 1
                    else :
                        xposdistribution[upos[j]] = 1
        
        acc = 0 
        for i in xposdistribution.items():
            acc += i[1]

        mod = 0 
        for i in xposdistribution.items():
            if mod < 3 :
                print(i[0] , "{:.1f}".format(i[1]/acc*100) , end="&")
            else :
                print(i[0] , "{:.1f}".format(i[1]/acc*100) , end="\\\\\n")
            
            mod = (mod + 1) % 4

                
    def semantic_syntactic_head_differences(self):

        headsalign = 0
        headsnotalign = 0


        for name , dataset in self.datasets.items():
            for j in dataset:
                vlocs : List[int] = j.get_verb_indices()
                heads = j.get_heads()
                srl = j.get_srl_annotation()
                if len(srl) > 0 :
                    for colindex in range(len(srl[0])):
                        for rowindex in range(len(srl)):

                            srlentry = srl[rowindex][colindex]
                            if srlentry != "V" and srlentry !="_":
                                if vlocs[rowindex] == heads[colindex]:
                                    headsalign += 1
                                else :
                                    headsnotalign += 1
        
        return headsalign , headsnotalign


    def pair_mapping_statistics(self):
        pairs = {} 
        for name , dataset in self.datasets.items():
            for j in dataset:
                dT = [*zip(*j.get_srl_annotation())]
                for x in dT:
                    for i in range(len(x)):
                        for j in range(i+1,len(x)):
                            if x[i] != "_" and x[j] != "_" and x[i] != "V" and x[j] != "V" :
                                pair = f"{x[i]}{x[j]}"
                                if pair in pairs:
                                    pairs[pair] +=1
                                else :
                                    pairs[pair] = 1 

        return pairs


    def role_proximity(self):
        nextisrole=0
        nextisnotrole = 0 
        for name , dataset in self.datasets.items():
            for j in dataset:
                dT = [*zip(*j.get_srl_annotation())]
                for x in dT:
                    if len([1 for b in x if b != "_" and b != "V"]) !=2:
                        continue
                    for i in range(len(x)-1):
                        j = i+1
                        if x[i] != "_" and x[j] != "_" and x[i] != "V" and x[j] != "V" :
                            # print(x[i],x[j])
                            nextisrole += 1
                        else:
                            # print(x[i],x[j])
                            nextisnotrole += 1


        return nextisrole , nextisnotrole





                


    def __iter__(self):    
        for i in self.datasets.items():
            yield i[1]

    