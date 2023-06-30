#! /usr/bin/env python
import os
import time
import argparse
import numpy as np
import pickle
from sklearn import datasets
from sklearn.metrics import confusion_matrix, accuracy_score
import tensorflow as tf
from model import Model
import pdfrw
import scipy

def parse_args():
    parser = argparse.ArgumentParser(description='Regular training and robust training of the pdf malware classification model.')
    parser.add_argument('--train', type=str, help='Training interval data.')
    parser.add_argument('--test', type=str, help='Testing interval data.', required=True)
    parser.add_argument('--test_batches', type=int, help='Number of testing batches', required=True)
    parser.add_argument('--seed_feat', type=str, help='Seed feature value pickle.')
    parser.add_argument('--exploit_spec', type=str, help='Exploit specification file.')
    parser.add_argument('--model_name', type=str, help='Save to this model.')
    parser.add_argument('--resume', action='store_true', default=False)
    parser.add_argument('--evaluate', action='store_true', default=False)
    parser.add_argument('--batch_size', type=int, default=50)
    # number of batches = epoch * (total_dataset_size / batch_size)
    parser.add_argument('--batches', type=int, default=30)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--lrdecay", type=float, default=1)
    parser.add_argument('--baseline', action='store_true', default=False)
    parser.add_argument('--verbose', type=int, default=500)
    return parser.parse_args()

def perf_measure(y_actual, y_hat):
    TP = 0
    FP = 0
    TN = 0
    FN = 0

    for i in range(len(y_hat)):
        if y_actual[i]==y_hat[i]==1:
           TP += 1
        if y_hat[i]==1 and y_actual[i]!=y_hat[i]:
           FP += 1
        if y_actual[i]==y_hat[i]==0:
           TN += 1
        if y_hat[i]==0 and y_actual[i]!=y_hat[i]:
           FN += 1

    return(TP, FP, TN, FN)

def eval(x, y, sess, model):
    y_p = sess.run(model.y_pred,\
                    feed_dict={model.x_input:x,\
                    model.y_input:y
                    })

    try:
        tn, fp, fn, tp = confusion_matrix(y, y_p).ravel()
        acc = (tp+tn)/float(tp+tn+fp+fn)
        fpr = fp/float(fp+tn)
        return acc, fpr
    except ValueError:
        return accuracy_score(y, y_p), None


def train(model):
    PATH = '../models/adv_trained/%s.ckpt' % args.model_name
    batch_size = args.batch_size
    batch_num = args.batches
    lr = args.lr

    learning_rate = tf.placeholder(tf.float32)

    loss = model.xent

    optimizer_op = tf.train.AdamOptimizer(learning_rate=\
                            learning_rate).minimize(loss)

    print('Loading regular training datasets...')
    train_data = '../data/traintest_all_500test/train_data.libsvm'
    x_train, y_train = datasets.load_svmlight_file(train_data,
                                       n_features=3514,
                                       multilabel=False,
                                       zero_based=False,
                                       query_id=False)

    x_train = x_train.toarray()

    print('Shuffle the training datasets...')
    x_train, y_train = shuffle_data(x_train, y_train)

    print('Loading regular testing datasets...')
    test_data = '../data/traintest_all_500test/test_data.libsvm'
    x_test, y_test = datasets.load_svmlight_file(test_data,
                                       n_features=3514,
                                       multilabel=False,
                                       zero_based=False,
                                       query_id=False)
    x_test = x_test.toarray()

    saver = tf.train.Saver()

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        sess.run(tf.local_variables_initializer())

        if(args.resume):
            saver.restore(sess, PATH)
            print("load model from:", PATH)
        else:
            print("initial model as:", PATH)

        j = 0
        epoch = 0
        for cur_batch in range(batch_num):
            start_time = time.time()
            x_batch = x_train[j:j+batch_size]
            y_batch = y_train[j:j+batch_size]
            l, acc, fpr, op = sess.run([loss, model.accuracy_op,\
                    model.false_positive_op, optimizer_op],\
                    feed_dict={model.x_input:x_batch,
                        model.y_input:y_batch,
                        learning_rate:lr}
                                )
            # start over.
            j += batch_size
            if j+batch_size > x_train.shape[0]:
                j = 0
                epoch += 1
                # number of batches = epoch * (total_dataset_size / batch_sizie

                if(epoch != 0 and epoch%10==0):
                    lr*=args.lrdecay
                    print("epoch:", epoch, " loss:",l, "train acc:", acc, "train fpr:", fpr, "epoch time:", time.time()-start_time)

                if(epoch != 0 and epoch%20==0):
                    test_acc, test_fpr = eval(x_test, y_test, sess, model)
                    print("epoch:", epoch, "eval test acc:", test_acc, "eval test fpr:", test_fpr)

        epoch = batch_num * batch_size / x_train.shape[0]
        print("epoch:", epoch, " loss:",l, "train acc:", acc, "epoch time:", time.time()-start_time)

        test_acc, test_fpr = eval(x_test, y_test, sess, model)
        print("epoch:", epoch, "eval test acc:", test_acc, "eval test fpr:", test_fpr)

        saver.save(sess, save_path=PATH)
        print("Model saved to", PATH)

def shuffle_data(x, y):
    idx = np.arange(0 , len(x))
    np.random.shuffle(idx)
    x_shuffle = np.array([x[i] for i in idx])
    y_shuffle = np.array([y[i] for i in idx])
    return x_shuffle, y_shuffle


def new_baseline_adv_train(model, train_interval_path, test_interval_path, model_name):
    PATH = '../models/adv_trained/%s.ckpt' % model_name
    batch_size = args.batch_size
    batch_num = args.batches
    lr = args.lr

    learning_rate = tf.placeholder(tf.float32)

    #for regular training
    regular_loss = model.xent
    optimizer_op = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(regular_loss)

    print('Loading regular training datasets...')
    train_data = '../data/traintest_all_500test/train_data.libsvm'
    x_train, y_train = datasets.load_svmlight_file(train_data,
                                       n_features=3514,
                                       multilabel=False,
                                       zero_based=False,
                                       query_id=False)
    x_train = x_train.toarray()

    print('x_train.shape:', x_train.shape)

    print('Loading regular testing datasets...')
    test_data = '../data/traintest_all_500test/test_data.libsvm'
    x_test, y_test = datasets.load_svmlight_file(test_data,
                                       n_features=3514,
                                       multilabel=False,
                                       zero_based=False,
                                       query_id=False)
    x_test = x_test.toarray()

    print('x_test.shape:', x_test.shape)

    # load the interval bound datasets. they will be used for adversarial retraining.
    print('Loading the training interval datasets...')
    y_input = pickle.load(open(os.path.join(train_interval_path, 'y_input.pickle'), 'rb'), encoding="latin1")
    vectors_all = pickle.load(open(os.path.join(train_interval_path, 'vectors_all.pickle'), "rb"), encoding="latin1")

    print('vectors_all.shape:', vectors_all.shape)

    # Load the test data
    print('Loading the testing interval datasets...')
    y_input_test = pickle.load(open(os.path.join(test_interval_path, 'y_input.pickle'), 'rb'), encoding="latin1")
    splits_test = pickle.load(open(os.path.join(test_interval_path, 'splits.pickle'), 'rb'), encoding="latin1")
    vectors_all_test = pickle.load(open(os.path.join(test_interval_path, 'vectors_all.pickle'), "rb"), encoding="latin1")

    print('vectors_all_test.shape:', vectors_all_test.shape)

    saver = tf.train.Saver()

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        sess.run(tf.local_variables_initializer())

        if(args.resume):
            saver.restore(sess, PATH)
            print("load model from:", PATH)
        else:
            print("initial model as:", PATH)

        j = 0
        i = 0
        epoch = 0
        print('Concatenate the training datasets...')
        all_x_train = np.concatenate((x_train, vectors_all))
        all_y_train = np.concatenate((y_train, y_input))

        print('all_x_train.shape:', all_x_train.shape)
        print('all_y_train.shape:', all_y_train.shape)

        print('Shuffle the training datasets...')
        all_x_train, all_y_train = shuffle_data(all_x_train, all_y_train)

        for cur_batch in range(batch_num):
            start_time = time.time()

            # regular training
            reg_l, reg_acc, fpr, op = sess.run([regular_loss, model.accuracy_op,\
                model.false_positive_op, optimizer_op],\
                feed_dict={model.x_input:all_x_train[j:j+batch_size],
                    model.y_input:all_y_train[j:j+batch_size],
                    learning_rate:lr}
                            )
            if j+batch_size > all_x_train.shape[0]:
                # last batch within this epoch
                reg_l, reg_acc, fpr, op = sess.run([regular_loss, model.accuracy_op,\
                    model.false_positive_op, optimizer_op],\
                    feed_dict={model.x_input:all_x_train[j:],
                        model.y_input:all_y_train[j:],
                        learning_rate:lr}
                                )
                epoch += 1
                print('Finished epoch %d...' % epoch)
                print('Shuffle the training datasets...')
                all_x_train, all_y_train = shuffle_data(all_x_train, all_y_train)
                j = 0
            else:
                j += batch_size
            if cur_batch != 0 and cur_batch % args.verbose ==0:
                lr*=args.lrdecay
                print("batch_num:", cur_batch, "regular loss:", reg_l, "regular train acc:", reg_acc , "epoch time:", time.time()-start_time)
                acc, fpr = eval(x_test, y_test, sess, model)
                print("*** test acc:", acc, "test fpr:, ", fpr)

        print('======= DONE =======')
        acc, fpr = eval(x_test, y_test, sess, model)
        print("======= test acc:", acc, "test fpr:", fpr)

        saver.save(sess, save_path=PATH)
        print("Model saved to", PATH)



def main(args):

    # Initialize the model

    model = Model()

    if(not args.evaluate):
        if(args.baseline):
            train(model)
            return
        else:
            new_baseline_adv_train(model, args.train, args.test, args.model_name)
            return

    if(args.baseline):
        PATH = "../models/adv_trained/baseline_checkpoint.ckpt"
    else:
        PATH = '../models/adv_trained/%s.ckpt' % args.model_name

    if PATH is None:
        print('No model found')
        SystemExit.exit()


if __name__=='__main__':
    args = parse_args()
    main(args)

