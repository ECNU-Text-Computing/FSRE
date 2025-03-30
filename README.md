# Few-shot medical relation extraction via prompt tuning enhanced pre-trained language model
The code of the paper [Few-shot medical relation extraction via prompt tuning enhanced pre-trained language model](https://www.sciencedirect.com/science/article/pii/S0925231225004242). This paper has been accepted to Neurocomputing.

### Abstract
We propose a prompt-enhanced few-shot relation extraction (FSRE) model that leverages few-shot and prompt learning techniques to improve performance with minimal data. Our approach introduces a hard prompt concatenated to the original input, enabling contextually enriched learning. We calculate prototype representations by averaging the intermediate states of each relation class in the support set, and classify relations by finding the shortest distance between the query instance and class prototypes. 

<!-- ### Environments
- ``python 3``
- ``PyTorch 1.7.1``
- ``transformers 4.6.0`` -->

### Datasets
We evaluate our model using three biomedical datasets: the [2010 i2b2/VA challenge dataset](https://doi.org/10.1136/amiajnl-2011-000203), the [CHEMPROT corpus](https://biocreative.bioinformatics.udel.edu/tasks/biocreative-vi/track-5/), and the [BioRED dataset](https://doi.org/10.1093/bib/bbac282).

To assess the performance of FSRE with limited amount of training data and to facilitate a comparative analysis with traditional BERT models on relation extraction tasks, we perform very hard restrictions of data partitioning on the dataset.

For demonstration, we have uploaded the sampled data from 2010 i2b2/VA challenge dataset in the **data** folder. As shown in [Figure 1](./figures/Training_Settings_Fig3.pdf), for this dataset, we randomly select three out of the total eight classes. For the validation set, we choose five classes, with each class containing 50 instances. Among these five classes, three are consistent with the training set, while the other two are selected at random. Regarding the test set, we randomly select 2,000 query instances, ensuring representation from all eight classes in the dataset.

### Model Training

### Code
Put all data in the **data** folder, CP pretrained model in the **CP_model** folder (you can download CP model from https://github.com/thunlp/RE-Context-or-Names/tree/master/pretrain), and then you can use the script *run_train.sh* to train the model.

#### Train
Set the corresponding parameter values in the script, and then run:
```
sh run_train.sh
```
Some explanations of the parameters in the script:
```
--pretrain_ckpt
	the path for the BERT-base-uncased
--backend_model
	bert or cp, select one backend model
--train_iter
	num of iters in training
--val_iter
	num of iters in validation
--test_iter
	num of iters in testing
--val_step
	val after training how many iters
--model
	the model used under **models** folder
--load_ckpt
	the path of the trained model
--add_prompt
	whether to add prompt information in the front or back, value = front/back/None
```

### Citation
He, G., & Huang, C. (2025). Few-shot medical relation extraction via prompt tuning enhanced pre-trained language model. Neurocomputing, 129752.
