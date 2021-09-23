import os
from re import L
import sys
from pathlib import Path
from flair import embeddings

from flair.embeddings.token import CharacterEmbeddings, FlairEmbeddings, TransformerWordEmbeddings

from semantictagger.conllu import CoNLL_U
from semantictagger.reconstructor import ReconstructionModule
from semantictagger.dataset import Dataset
from semantictagger.paradigms import SEQTAG
from semantictagger.selectiondelegate import SelectionDelegate

from flair.data import Corpus , Sentence 
from flair.datasets import ColumnCorpus
from flair.embeddings import StackedEmbeddings , ELMoEmbeddings , OneHotEmbeddings
from flair.models import SequenceTagger
from flair.trainers import ModelTrainer

from math import ceil

import ccformat
import flair,torch

from typing import List
import logging
import uuid 

import logging
import eval 


import argparse

parser = argparse.ArgumentParser(description='SEQTagging for SRL Training Script.')
parser.add_argument('--POS-GOLD', type = bool , help='Use GOLD for XPOS/UPOS.')
parser.add_argument('--PREDICATE-GOLD', type = bool , help='Use GOLD for predicates.')

args = parser.parse_args()
GOLDPREDICATES = args.PREDICATE_GOLD
GOLDPOS = args.POS_GOLD
if GOLDPREDICATES is None or GOLDPOS is None:
    Exception("Missing arguments. Use -h option to see what option you should be using.")



#create a logger
logger = logging.getLogger('res')

handler = logging.FileHandler('results.log')
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

flair.device = torch.device('cuda:1')
curdir = os.path.dirname(__file__)
sys.setrecursionlimit(100000)

test_frame_file = Path("./test/test_frame.tsv")
test_pos_file = Path("./test/test_pos.tsv")

dev_frame_file = Path("./test/dev_frame.tsv")
dev_frame_file = Path("./test/dev_frame.tsv")



def rescuefilesfromModification():
    # Save models from being overwritten.
    modeldir =os.path.join(curdir,'modelout')
    for item in os.listdir(modeldir):
        if os.path.isfile(os.path.join(modeldir, item)):
            saved_file = os.path.join(modeldir , item)
            new_location = os.path.join(modeldir , 'tmp' , item)
            print(f"File Rescue : {saved_file} is being moved to {new_location}")
            os.rename(saved_file , new_location)


train_file = Path("./UP_English-EWT/en_ewt-up-train.conllu")
test_file = Path("./UP_English-EWT/en_ewt-up-test.conllu")
dev_file = Path("./UP_English-EWT/en_ewt-up-dev.conllu")
dataset_train = Dataset(train_file)
dataset_test = Dataset(test_file)
dataset_dev = Dataset(dev_file)
    
tagdictionary  = dataset_train.tags
counter = 1 
for i in tagdictionary:
    tagdictionary[i] = counter
    counter += 1
tagdictionary["UNK"] = 0


sd = SelectionDelegate([lambda x: [x[0]]])
rm = ReconstructionModule()


tagger = SEQTAG(
        mult=3 ,
        selectiondelegate=sd,
        reconstruction_module=rm,
        tag_dictionary=tagdictionary,
        rolehandler="complete" ,
        verbshandler="omitverb",
        verbsonly=False, 
        deprel=True
        )



data = ["train.tsv" , "test.tsv" , "dev.tsv","train_frame.tsv","test_frame.tsv","dev_frame.tsv","train_pos.tsv","dev_pos.tsv","test_pos.tsv"]
for i in range(len(data)) :
    pathtodata = os.path.join(curdir,"data",data[i])
    if os.path.isfile(pathtodata):
        os.remove(pathtodata)


ccformat.writecolumncorpus(dataset_train , tagger, filename="train" , frame_gold = GOLDPREDICATES , pos_gold = GOLDPOS)
ccformat.writecolumncorpus(dataset_dev , tagger, filename="dev",  frame_gold = GOLDPREDICATES , pos_gold = GOLDPOS)
ccformat.writecolumncorpus(dataset_test , tagger, filename="test" ,  frame_gold = GOLDPREDICATES , pos_gold = GOLDPOS)

if GOLDPREDICATES:
    # ccformat.writecolumncorpus(dataset_train , tagger, filename="train_frame",frameonly=True)
    ccformat.writecolumncorpus(dataset_dev , tagger, filename="dev_frame",  frameonly=True)
    ccformat.writecolumncorpus(dataset_test , tagger, filename="test_frame" , frameonly=True)

if GOLDPOS:
    # ccformat.writecolumncorpus(dataset_train , tagger, filename="train_pos",posonly=True)
    ccformat.writecolumncorpus(dataset_dev , tagger, filename="dev_pos",  posonly=True)
    ccformat.writecolumncorpus(dataset_test , tagger, filename="test_pos" , posonly=True)
    

if GOLDPOS and GOLDPREDICATES:
    columns = {0: 'text', 1: 'srl' , 2:'frame' , 3:'pos'}
elif GOLDPOS:
    columns = {0: 'text', 1: 'srl' , 3:'pos'}
elif GOLDPREDICATES:
    columns = {0: 'text', 1: 'srl' , 3:'frame'}
else :
    columns = {0: 'text', 1: 'srl' }


# init a corpus using column format, data folder and the names of the train, dev and test files
corpus: Corpus = ColumnCorpus(os.path.join(curdir,"data"),
                            columns,
                            train_file='train.tsv',
                            test_file='test.tsv',
                            dev_file='dev.tsv')


tag_type = 'srl'
tag_dictionary = corpus.make_tag_dictionary(tag_type=tag_type)


def train_lstm(hidden_size : int , lr : float , dropout : float , layer : int , locked_dropout = float , batch_size = int):

    elmo = ELMoEmbeddings("original-all")
    embeddings = [elmo]
    
    if not GOLDPOS:
        if tagger.postype == POSTYPE.UPOS:
            upostagger : SequenceTagger = SequenceTagger.load("flair/upos-english-fast")
            upostagger.predict(corpus.test, label_name="pos")
            upostagger.predict(corpus.train, label_name="pos")
            upostagger.predict(corpus.dev, label_name="pos")
            uposembeddings = OneHotEmbeddings(corpus=corpus, field="pos", embedding_length=17)
            upostagger.evaluate(corpus.dev ,out_path = "./data/dev_pos.tsv")
            upostagger.evaluate(corpus.test ,out_path = "./data/test_pos.tsv")
            embeddings.append(uposembeddings)


        else:
            xpostagger = SequenceTagger.load("flair/pos-english")
            xpostagger.predict(corpus.test, label_name="pos")
            xpostagger.predict(corpus.train, label_name="pos")
            xpostagger.predict(corpus.dev, label_name="pos")
            xposembeddings = OneHotEmbeddings(corpus=corpus, field="pos", embedding_length=41)
            xpostagger.evaluate(corpus.dev ,out_path = "./data/dev_pos.tsv")
            xpostagger.evaluate(corpus.test ,out_path = "./data/test_pos.tsv")
            embeddings.append(xposembeddings)

    if not GOLDPREDICATES:
        frametagger = SequenceTagger.load(f"./best_models/predonlymodel.pt")
        frametagger.predict(corpus.dev, label_name="frame")
        frametagger.predict(corpus.test, label_name="frame")
        frametagger.predict(corpus.train, label_name="frame")
        frameembeddings = OneHotEmbeddings(corpus=corpus, field="frame", embedding_length=3)
        frametagger.evaluate(corpus.dev ,out_path = "./data/dev_frame.tsv")
        frametagger.evaluate(corpus.test ,out_path = "./data/test_frame.tsv")
        
        embeddings.append(frameembeddings)
    

    stackedembeddings = StackedEmbeddings(
        embeddings= embeddings
    )

    randid = str(uuid.uuid1())[0:5]
    logger.info(str(stackedembeddings))
    

    sequencetagger = SequenceTagger(
        hidden_size=hidden_size ,
        embeddings= stackedembeddings ,
        tag_dictionary=tag_dictionary,
        tag_type=tag_type,
        use_crf=False,
        use_rnn= True,
        rnn_layers=1,
        dropout = dropout,
        locked_dropout=locked_dropout
    )


    path = f"model/{lr}-{hidden_size}-{layer}-{dropout}-{locked_dropout}"
    for l in embeddings :
        path += f"-{str(l)}"
    path += f"-{randid}"

    abc = ModelTrainer(sequencetagger,corpus).train(
        base_path= path,
        learning_rate=lr,
        mini_batch_chunk_size=batch_size,
        max_epochs=1,
        embeddings_storage_mode="cpu"
    )

         
   
    e = eval.EvaluationModule(
        paradigm  = tagger, 
        dataset = dataset_test,
        pathroles  = os.path.join(path,"test.tsv"),
        goldpos = GOLDPOS,
        goldframes = GOLDPREDICATES,
        path_frame_file  = test_frame_file ,
        path_pos_file  = test_pos_file,
        span_based = True,
        mockevaluation = False ,
        )

    e.createpropsfiles(debug = False)
    with os.popen(f'cd ./evaluation/conll05 ; perl srl-eval.pl target.tsv pred.tsv') as output:
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
                print(results)
                break
    if val:
        logger.info(f"{path}\t{abc['test_score']}\t CoNLL05 GOLD:{str(list(results.items()))}")
    else :
        logger.info(f"{path}\t{abc['test_score']}\t CoNLL05 :{str(list(results.items()))}")
    
    os.remove(path+"/best-model.pt")
    os.remove(path+"/final-model.pt")
    

train_lstm(hidden_size = 512 , lr = 0.2 , dropout =0.3 , layer = 1 , locked_dropout = 0.0 , batch_size=16)
