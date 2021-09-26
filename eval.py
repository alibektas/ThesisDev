from pathlib import Path, PureWindowsPath

from semantictagger import conllu
from semantictagger import paradigms
from semantictagger.conllu import CoNLL_U
from semantictagger.dataset import Dataset
from semantictagger.paradigms import Encoder
from semantictagger.datatypes import Outformat

from typing import Dict, Generator, Iterator , Tuple , Union
import os 
from pandas import DataFrame
from tqdm import tqdm
import pdb 
import enum



class EvaluationModule():

    def __init__(self, 
        paradigm : Encoder , 
        dataset : Dataset , 
        early_stopping : int,
        pathroles : Union[Path,str] , 
        path_frame_file : Union[Path,str] ,
        path_pos_file : Union[Path,str],
        goldframes : bool = False,
        goldpos : bool = False,
        mockevaluation : bool = False , 
        ):
        
        self.postype : paradigms.POSTYPE = paradigm.postype 
        self.early_stopping = early_stopping
        self.paradigm : Encoder = paradigm
        self.dataset : Dataset = dataset
        self.mockevaluation = mockevaluation
        self.goldpos = goldpos
        self.goldframes = goldframes

        if not self.mockevaluation :
            self.rolesgen : Iterator = iter(self.__readresults__(pathroles , gold = False))
            self.predgen : Iterator = iter(self.__readresults__(path_frame_file, gold = goldframes))
            self.posgen : Iterator = iter(self.__readresults__(path_pos_file , gold = goldpos))

       
        self.entryiter : Iterator = iter(self.dataset)
    
    def __readresults__(self , path , gold):
        """
            Flair outputs two files , called dev.tsv and test.tsv respectively.
            These files can be read with this function and each time this function 
            will yield one entry, which in theory should align with the corresponding dataset.
        """
        entryid = 0
        entry = ["" for d in range(100)]
        counter = 0 
        earlystoppingcounter = 0

        
        if type(path) == str:
            path = Path(path)

        with path.open() as f:
            while True:
                line = f.readline().replace("\n" , "").replace("\t" , " ")

                if line is None:
                    break

                if line == "" : 
                    entryid += 1
                    yield entry[:counter]
                    entry = ["" for d in range(100)] 
                    counter = 0
                    earlystoppingcounter +=1
                    if self.early_stopping != False:
                        if self.early_stopping == earlystoppingcounter :
                            return None
                else : 
                    
                    elems = line.split(" ")
                    if len(elems) == 1: 
                        entry[counter] = ""
                    elif len(elems) == 2:
                        if gold :
                            entry[counter] = elems[1]
                        else :
                            entry[counter] = ""
                    elif len(elems) == 3:
                        entry[counter] = elems[2]
                    counter += 1

        return None

    def single(self , verbose = False):
        
        try:
            target = next(self.entryiter)
        except StopIteration:
            return None
        
        
        words = target.get_words()


        if not self.mockevaluation:
            preds = next(self.predgen)
            pos = next(self.posgen)
            if preds is None:
                return None
            preds = ["V" if x != "" and x!= "_" else "_" for x in preds]
            roles = next(self.rolesgen)
            if roles is None:
                return None     
            predicted = self.paradigm.spanize(words , preds , roles , pos)

        else :
            roles = self.paradigm.encode(target)
            if self.postype == paradigms.POSTYPE.UPOS:
                pos = target.get_by_tag("upos")
            else :
                pos = target.get_by_tag("xpos")

            preds = ["V" if x != "" and x!= "_" else "_" for x in target.get_vsa()]
            predicted = self.paradigm.spanize(words , preds , roles , pos)

        
        if verbose:
            
            a = {"words":words , "predicates" : preds , "roles" : roles}
            a.update({f"TARGET {i}" : v for i  , v in enumerate(target.get_span())})
            a.update({f"PRED {i}" : v for i  , v in enumerate(predicted.get_span())})

            return DataFrame(a)
    

        return target , predicted , roles

    def createpropsfiles(self, saveloc , debug = False):

        counter = -1

        outfiles = [
            (Outformat.CONLL05 , ("predicted-props.tsv","target-props.tsv")),
            (Outformat.CONLL09 , ("predicted-props-conll09.tsv","target-props-conll09.tsv"))
        ]
        
        
        for of in outfiles:
            with open(os.path.join(saveloc , of[1][0] ) , "x") as fp:
                with open(os.path.join(saveloc , of[1][1]) , "x") as ft:
                    total = len(self.dataset)
                    if self.early_stopping != False:
                        total = min(len(self.dataset),self.early_stopping)
                    for i in tqdm(range(total)):
                        s = self.single()
                        
                        if s is None :
                            return 
                        
                        target , predicted , roles = s[0] , s[1] , s[2]
                        
                        files = (fp , ft)
                        entries = (predicted , target)
                        counter += 1 

                        for k in range(2):                     
                            if of[0] == Outformat.CONLL05:
                                if k == 0 :
                                    spans = predicted
                                else:
                                    spans = entries[k].get_span()
                            # elif of[0] == Outformat.CoNLL09:
                            else:
                                spans = entries[k].get_depbased()

                            
                            
                            vsa = entries[1].get_vsa()
                            if of[0] == Outformat.CONLL05:
                                vsa = ["V" if a != "_" and a != "" else "-" for a in vsa]
                            words = entries[1].get_words()
                            
                            if debug:
                                files[k].write(f"{counter}\n")

                            for i in range(len(vsa)):
                                
                                if debug:
                                    files[k].write(f"{words[i]}\t")
                                    files[k].write(f"{roles[i]}\t")

                                files[k].write(f"{vsa[i]}\t")
                            


                                for j in range(len(spans)):
                                    files[k].write(f"{spans[j][i]}\t")
                                files[k].write("\n")
                            files[k].write("\n")

    def evaluate(self , path):
        return { 
            "conll09" : self.evaluate_conll09(path),
            "conll05" : self.evaluate_conll05(path)
        }


# 'perl ./evaluation/conll09/eval09.pl -g model/upos/goldpos/goldframes/1.0-1-1-0.2-0.1-0-glove-english-4db55/target-props-conll09.tsv -s model/upos/goldpos/goldframes/1.0-1-1-0.2-0.1-0-glove-english-4db55/predicted-props-conll09.tsv'

    def evaluate_conll09(self,path):
        
        with os.popen(f'perl ./evaluation/conll09/eval09.pl -g {path}/target-props-conll09.tsv -s {path}/predicted-props-conll09.tsv') as output:
            while True:
                line = output.readline()
                if not line: break
                line = re.sub(" +" , " " , line)
                array = line.strip("").strip("\n").split(" ")
                if len(array) > 2 and array[1] == "Overall": 
                    results = {   
                        "correct" : np.float(array[2]), 
                        "excess" : np.float(array[3]),
                        "missed" : np.float(array[4]),
                        "recall" : np.float(array[5]),
                        "precision" : np.float(array[6]),
                        "f1" : np.float(array[7])
                    }
                    conll05terminates = True
                    return results
        
        return None

    def evaluate_conll05(self,path):
        
        with os.popen(f'perl ./evaluation/conll05/srl-eval.pl {path}/target-props.tsv {path}/predicted-props.tsv') as output:
            while True:
                line = output.readline()
                print(line)
                if not line: break
                line = re.sub(" +" , " " , line)
                array = line.strip("").strip("\n").split(" ")
                if len(array) > 2 and array[1] == "Overall": 
                    results = {   
                        "correct" : np.float(array[2]), 
                        "excess" : np.float(array[3]),
                        "missed" : np.float(array[4]),
                        "recall" : np.float(array[5]),
                        "precision" : np.float(array[6]),
                        "f1" : np.float(array[7])
                    }
                    conll05terminates = True
                    return results
        
        return None