"""
Created on Thu Jan  7 09:35:55 2021
All rights reserved

@author: Javier Fumanal Idocin - University of Essex
@author: Javier Andreu-Perez - University of Essex


This is a the source file that contains a demo for a tip computation example, where a diferent set of T1-FS are used to compute
a t1 reasoning approach.

We also show the GA to optimize the rules obtained in classification.

"""


import pandas as pd

from sklearn import datasets
from sklearn.model_selection import train_test_split

import sys

# In case you run this without installing the package, you need to add the path to the package

# This is for launching from root folder path
sys.path.append('./ex_fuzzy/')
sys.path.append('./ex_fuzzy/ex_fuzzy/')

# This is for launching from Demos folder
sys.path.append('../ex_fuzzy/')
sys.path.append('../ex_fuzzy/ex_fuzzy/')


import ex_fuzzy.fuzzy_sets as fs
import ex_fuzzy.evolutionary_fit as GA
import ex_fuzzy.utils as  utils
import ex_fuzzy.eval_tools as eval_tools
import ex_fuzzy.persistence as persistence
import ex_fuzzy.vis_rules as vis_rules


runner = 1 # 1: single thread, 2+: corresponding multi-thread

n_gen = 50
n_pop = 50
    
nRules = 15
nAnts = 4
vl = 3
tolerance = 0.01
fz_type_studied = fs.FUZZY_SETS.t2

# Import some data to play with
iris = datasets.load_iris()
X = pd.DataFrame(iris.data, columns=iris.feature_names)
y = iris.target

# Compute the fuzzy partitions using 3 quartiles
precomputed_partitions = utils.construct_partitions(X, fz_type_studied)

# Split the data into a training set and a test set
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, random_state=0)

# We create a FRBC with the precomputed partitions and the specified fuzzy set type, 
fl_classifier = GA.BaseFuzzyRulesClassifier(nRules=nRules, linguistic_variables=precomputed_partitions, nAnts=nAnts, 
                                            n_linguist_variables=vl, fuzzy_type=fz_type_studied, verbose=False, tolerance=tolerance, runner=runner)
# fl_classifier.customized_loss(utils.mcc_loss)
fl_classifier.fit(X_train, y_train, n_gen=n_gen, pop_size=n_pop, checkpoints=0, random_state=0)
print(vis_rules.rules_to_latex(fl_classifier.rule_base))
str_rules = eval_tools.eval_fuzzy_model(fl_classifier, X_train, y_train, X_test, y_test, 
                        plot_rules=True, print_rules=True, plot_partitions=True, return_rules=True)

# Save the rules as a plain text file
with open('rules_iris_t2.txt', 'w') as f:
    f.write(str_rules)

print('Done')