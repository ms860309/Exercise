#!/usr/bin/env python
# -*- coding:utf-8 -*-

import numpy as np
import keras.backend as K
from keras.engine.topology import Layer
from keras.models import Model


class EnsembleModel(Model):
    def __init__(self, seeds=[None], **kwargs):
        super(EnsembleModel, self).__init__(**kwargs)
        self.grad_model = None
        self.seeds = seeds
        self.weight_generators = None
        self.mask_id = 0
        self.generated_masks = False

    def gen_masks(self):
        rngs = []
        for seed in self.seeds:
            rng = np.random.RandomState()
            if seed is not None:
                rng.seed(seed)
            rngs.append(rng)
        for layer in self.layers:
            if 'gen_masks' in dir(layer):
                layer.gen_masks(rngs)
        self.generated_masks = True

    def set_mask(self, idx):
        if not self.generated_masks:
            self.gen_masks()
        for layer in self.layers:
            if 'set_mask' in dir(layer):
                layer.set_mask(idx)
        
    def reset_mask_id(self):
        self.mask_id = 0        

    def train_on_batch(self, x, y, **kwargs):   
        idx = np.random.choice(len(self.seeds))
        self.set_mask(idx)
        loss = super(EnsembleModel,self).train_on_batch(x, y, **kwargs)
        return loss

    def test_on_batch(self, x, y, **kwargs):   
        idx = np.random.choice(len(self.seeds))
        self.set_mask(idx)
        loss = super(EnsembleModel,self).test_on_batch(x, y, **kwargs)
        return loss
    
    def test_model(self, x, y, **kwargs):   
        Y = []
        for j in range(len(self.seeds)):
            print 'mask {}'.format(j)
            self.set_mask(j)
            Y += [super(EnsembleModel,self).predict(x, **kwargs)] 
        Y_avg = np.mean(Y,axis=0)
        Y_var = np.var(Y,axis=0)
        f = open('test_output.txt','w')
        for i, Y_true in enumerate(y):
            f.write('{} {} {}\n'.format(y[i], Y_avg[i][0], Y_var[i][0]))

    def predict(self, x, sigma=False, **kwargs):
        Y = []
        for j in range(len(self.seeds)):
            self.set_mask(j)
            Y += [super(EnsembleModel,self).predict(x, **kwargs)] 
        Y_avg = np.mean(Y,axis=0)
        if sigma:
            Y_sigma = np.std(Y,axis=0)
            return Y_avg, Y_sigma
        return Y_avg   
    
    def get_config(self):
        config = super(EnsembleModel, self).get_config()
        config['seeds'] = self.seeds
        return config
    
    @classmethod
    def from_config(cls, config, custom_objects=None):
        model = super(EnsembleModel, cls).from_config(config, custom_objects=custom_objects)
        model.seeds = config.get('seeds')
        return model


class RandomMask(Layer):
    """Applies Mask to the input.
    """
    
    def __init__(self, dropout_rate, **kwargs):
        self.dropout_rate = dropout_rate
        self.vals = []
        super(RandomMask, self).__init__(**kwargs)

    def call(self, x, **kwargs):
        size = K.int_shape(x)[1:]
        self.mask = K.variable(np.ones(shape=size,dtype=np.float32))
        x *= self.mask
        return x
    
    def gen_masks(self, rngs):
        for rng in rngs:
            retain_prob = 1.0 - self.dropout_rate
            size = K.int_shape(self.mask)
            self.vals.append(rng.binomial(n=1, p=retain_prob, size=size).astype(np.float32))

    def set_mask(self, idx):
        K.set_value(self.mask, self.vals[idx])

    def get_config(self):
        config = {'dropout_rate': self.dropout_rate}
        base_config = super(RandomMask, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))
