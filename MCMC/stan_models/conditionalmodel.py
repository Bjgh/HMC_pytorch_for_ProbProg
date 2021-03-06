#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Author: Bradley Gram-Hansen
Time created:  09:11
Date created:  26/09/2017

License: MIT
'''

import pickle
import matplotlib.pyplot as plt
import numpy as np
np.random.seed(1234)
import pystan

model_code =''' 
data {
    real y;
}

parameters {
      
      real x;

}

model {
     x ~ normal(0, 1);
     if (x >= 0)
        target += normal_lpdf(y | 1,1);
     else
        target += normal_lpdf(y | -1,1);
}
     
        
 '''
# set up the model
def initfun():
    return  dict(y=1)
model = pystan.stan(model_code=model_code, data=initfun(),iter=10000, chains=4)
print(model)

trace = model.extract()
print(trace)
dat = trace['x'][:]
plt.figure(figsize=(10,4))
plt.hist(dat, bins ='auto', normed=1)
plt.savefig('conditionalif.png')
print('Completed plots')
# # PyStan uses pickle to save objects for future use.
# with open('model.pkl', 'wb') as f:
#     pickle.dump(model,f)
#
# with open('model.pkl', 'rb') as f:
#     model = pickle.load(f)
#
# print(model)
