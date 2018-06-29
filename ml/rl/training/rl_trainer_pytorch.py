#!/usr/bin/env python3

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

from ml.rl.thrift.core.ttypes import AdditionalFeatureTypes

DEFAULT_ADDITIONAL_FEATURE_TYPES = AdditionalFeatureTypes(int_features=False)


class RLTrainer:
    def __init__(self, parameters, use_gpu, additional_feature_types):

        self.minibatch = 0
        self.reward_burnin = parameters.rl.reward_burnin
        self._additional_feature_types = additional_feature_types
        self.rl_temperature = parameters.rl.temperature
        self.gamma = parameters.rl.gamma
        self.tau = parameters.rl.target_update_rate
        self.use_seq_num_diff_as_time_diff = parameters.rl.use_seq_num_diff_as_time_diff

        if use_gpu and torch.cuda.is_available():
            self.use_gpu = True
            self.dtype = torch.cuda.FloatTensor
            self.dtypelong = torch.cuda.LongTensor
        else:
            self.use_gpu = False
            self.dtype = torch.FloatTensor
            self.dtypelong = torch.LongTensor

    def _set_optimizer(self, optimizer_name):
        if optimizer_name == "ADAM":
            self.optimizer_func = torch.optim.Adam
        elif optimizer_name == "SGD":
            self.optimizer_func = torch.optim.SGD
        else:
            raise NotImplementedError(
                "{} optimizer not implemented".format(optimizer_name)
            )

    def _soft_update(self, network, target_network, tau) -> None:
        """ Target network update logic as defined in DDPG paper
        updated_params = tau * network_params + (1 - tau) * target_network_params
        :param network network with parameters to include in soft update
        :param target_network target network with params to soft update
        :param tau hyperparameter to control target tracking speed
        """
        for t_param, param in zip(target_network.parameters(), network.parameters()):
            new_param = tau * param.data + (1.0 - tau) * t_param.data
            t_param.data.copy_(new_param)

    def train(self, training_samples, evaluator=None, episode_values=None) -> None:
        raise NotImplementedError()


class GenericFeedForwardNetwork(nn.Module):
    def __init__(self, layers, activations) -> None:
        super(GenericFeedForwardNetwork, self).__init__()
        self.layers: nn.ModuleList = nn.ModuleList()
        self.batch_norm_ops: nn.ModuleList = nn.ModuleList()
        self.activations = activations

        assert len(layers) >= 2, "Invalid layer schema {} for network".format(layers)

        for i, layer in enumerate(layers[1:]):
            self.layers.append(nn.Linear(layers[i], layer))
            self.batch_norm_ops.append(nn.BatchNorm1d(layers[i]))

    def forward(self, input) -> torch.FloatTensor:
        """ Forward pass for generic feed-forward DNNs. Assumes activation names
        are valid pytorch activation names.
        :param input tensor
        """
        if isinstance(input, np.ndarray):
            input = Variable(torch.from_numpy(input))

        x = input
        for i, activation in enumerate(self.activations):
            # TODO: (edoardoc) T30535967 Renable batchnorm when T30535876 is fixed
            # x = self.batch_norm_ops[i](x)
            activation_func = getattr(F, activation)
            fc_func = self.layers[i]
            x = fc_func(x) if activation == "linear" else activation_func(fc_func(x))
        return x
