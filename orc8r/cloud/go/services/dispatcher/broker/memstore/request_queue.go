/*
Copyright (c) Facebook, Inc. and its affiliates.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree.
*/

package memstore

import (
	"errors"
	"fmt"
	"sync"
	"time"

	"magma/orc8r/cloud/go/protos"
)

// InitializedQueue contains an initialized NewQueue, and an OldQueue to cleanup if any
type InitializedQueue struct {
	NewQueue chan *protos.SyncRPCRequest
	OldQueue chan *protos.SyncRPCRequest
}

type RequestQueue interface {
	InitializeQueue(gwId string) InitializedQueue
	CleanupQueue(gwId string) chan *protos.SyncRPCRequest
	Enqueue(req *protos.SyncRPCRequest) error
}

type requestQueueImpl struct {
	reqQueueByGwId map[string]chan *protos.SyncRPCRequest
	*sync.RWMutex
	maxQueueLen int
}

func NewRequestQueue(queueLen int) *requestQueueImpl {
	return &requestQueueImpl{
		make(map[string]chan *protos.SyncRPCRequest),
		&sync.RWMutex{},
		queueLen,
	}
}

// returns new queue to dequeue from, and old queue to clean up
func (queues *requestQueueImpl) InitializeQueue(gwId string) InitializedQueue {
	queues.Lock()
	defer queues.Unlock()
	newQueue := make(chan *protos.SyncRPCRequest, queues.maxQueueLen)
	if oldQueue, ok := queues.reqQueueByGwId[gwId]; ok {
		// sends on a closed queue will panic, but no one will send onto this queue,
		// because all sends are through enqueue.
		close(oldQueue)
		queues.reqQueueByGwId[gwId] = newQueue
		return InitializedQueue{newQueue, oldQueue}
	}
	queues.reqQueueByGwId[gwId] = newQueue
	return InitializedQueue{newQueue, nil}
}

// return old queue to clean up
func (queues *requestQueueImpl) CleanupQueue(gwId string) chan *protos.SyncRPCRequest {
	queues.Lock()
	defer queues.Unlock()
	if queue, ok := queues.reqQueueByGwId[gwId]; ok {
		// sends on a closed queue will panic, but no one will send onto this queue,
		// because all sends are through enqueue.
		close(queue)
		delete(queues.reqQueueByGwId, gwId)
		// the broker will cleanup requests in the queue
		return queue
	}
	return nil
}

// Adds a SyncRPCRequest to the queue of gatewayId gwId. gwId cannot be empty string,
// gwReq or ReqId of gwReq cannot be nil
// gwId: key of the syncRPCReqQueue map
// gwReq: to append to []protos.SyncRPCRequest of the syncRPCReqQueue
func (queues *requestQueueImpl) Enqueue(gwReq *protos.SyncRPCRequest) error {
	if gwReq == nil || gwReq.ReqId <= 0 || gwReq.ReqBody == nil || len(gwReq.ReqBody.GwId) == 0 {
		return errors.New("SyncRPCRequest cannot be nil and gwId of ReqBody has to be valid")
	}
	gwId := gwReq.ReqBody.GwId
	queues.RLock()
	defer queues.RUnlock()
	reqQueue, ok := queues.reqQueueByGwId[gwId]
	if !ok {
		return errors.New(fmt.Sprintf("Queue does not exist for gwId %v\n", gwId))
	}
	select {
	case reqQueue <- gwReq:
		return nil
	case <-time.After(time.Second):
		return errors.New(fmt.Sprintf("Failed to enqueue %v because queue for gwId %v is full\n", gwReq, gwId))
	}
}
