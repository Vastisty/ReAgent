#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates. All rights reserved.
import logging
from enum import Enum

import reagent.types as rlt
import torch
from reagent.core.dataclasses import field
from reagent.models.base import ModelBase
from reagent.optimizer.union import Optimizer__Union
from reagent.training.trainer import Trainer


logger = logging.getLogger(__name__)


class LossFunction(Enum):
    MSE = "MSE_LOSS"
    SmoothL1Loss = "SmoothL1_Loss"
    L1Loss = "L1_Loss"


def _get_loss_function(loss_fn: LossFunction):
    if loss_fn == LossFunction.MSE:
        return torch.nn.MSELoss(reduction="mean")
    elif loss_fn == LossFunction.SmoothL1Loss:
        return torch.nn.SmoothL1Loss(reduction="mean")
    elif loss_fn == LossFunction.L1Loss:
        return torch.nn.L1Loss(reduction="mean")


class RewardNetTrainer(Trainer):
    def __init__(
        self,
        reward_net: ModelBase,
        use_gpu: bool = False,
        minibatch_size: int = 1024,
        optimizer: Optimizer__Union = field(  # noqa: B008
            default_factory=Optimizer__Union.default
        ),
        loss_type: LossFunction = LossFunction.MSE,
    ) -> None:
        self.reward_net = reward_net
        self.use_gpu = use_gpu
        self.minibatch_size = minibatch_size
        self.minibatch = 0
        self.opt = optimizer.make_optimizer(self.reward_net.parameters())
        self.loss_type = loss_type
        self.loss_fn = _get_loss_function(loss_type)

    def train(self, training_batch: rlt.PreprocessedTrainingBatch):
        training_input = training_batch.training_input
        if isinstance(training_input, rlt.PreprocessedRankingInput):
            target_reward = training_input.slate_reward
        else:
            target_reward = training_input.reward

        predicted_reward = self.reward_net(training_input).predicted_reward
        loss = self.loss_fn(predicted_reward, target_reward)
        self.opt.zero_grad()
        loss.backward()
        self.opt.step()
        loss = loss.detach()

        self.minibatch += 1
        if self.minibatch % 10 == 0:
            logger.info(f"{self.minibatch}-th batch: {self.loss_type}={loss}")

        return loss

    def warm_start_components(self):
        return ["reward_net"]
