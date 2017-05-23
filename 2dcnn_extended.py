from tomography import SampleGenerator
import tensorflow as tf
import numpy as np

# (batch, in_height, in_width, in_channels)
x = tf.placeholder(tf.float32, [None, 66, 66, 9])
y = tf.placeholder(tf.int64, [None])


with tf.variable_scope('conv1') as scope:
    out_filters = 64
    kernel = tf.get_variable('wieghts', [5, 5, 9, out_filters], tf.float32,
                             tf.truncated_normal_initializer(stddev=0.1))
    conv = tf.nn.conv2d(x, filter=kernel, strides=[1, 1, 1, 1], padding='SAME')
    mean, var = tf.nn.moments(conv, [0, 1, 2])
    conv = tf.nn.batch_normalization(conv, mean, var, 0, 1, 0.0001)  # BN
    biases = tf.get_variable('biases', [out_filters], tf.float32,
                             tf.constant_initializer(0.1, dtype=tf.float32))
    bias_added = tf.nn.bias_add(conv, biases)
    # activate
    conv1 = tf.nn.relu(bias_added, name=scope.name)  # activate

# max-pooling
# TODO: ksize? strides?
pool1 = tf.nn.max_pool(conv1, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1],
                       padding='SAME')
in_filters = out_filters
print('conv1 layer ready')

with tf.variable_scope('conv2') as scope:
    out_filters = 32
    kernel = tf.get_variable('weights', [3, 3, in_filters, out_filters],
                             tf.float32, tf.truncated_normal_initializer(stddev=0.1))
    conv = tf.nn.conv2d(pool1, filter=kernel, strides=[1, 1, 1, 1], padding='SAME')
    mean, var = tf.nn.moments(conv, [0, 1, 2])
    conv = tf.nn.batch_normalization(conv, mean, var, 0, 1, 0.0001)  # BN
    biases = tf.get_variable('biases', [out_filters], tf.float32,
                             tf.constant_initializer(0.1, dtype=tf.float32))
    bias_added = tf.nn.bias_add(conv, biases)
    conv2 = tf.nn.relu(bias_added, name=scope.name) # activate
print('conv2 layer ready')

# max pooling
pool2 = tf.nn.max_pool(conv2, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
in_filters = out_filters

with tf.variable_scope('conv3') as scope:
    out_filters = 16
    kernel = tf.get_variable('weights', [3, 3, in_filters, out_filters],
                             tf.float32, tf.truncated_normal_initializer(stddev=0.1))
    conv = tf.nn.conv2d(pool2, filter=kernel, strides=[1, 1, 1, 1], padding='SAME')
    mean, var = tf.nn.moments(conv, [0, 1, 2])
    conv = tf.nn.batch_normalization(conv, mean, var, 0, 1, 0.0001)  # BN
    biases = tf.get_variable('biases', [out_filters], tf.float32,
                             tf.constant_initializer(0.1, dtype=tf.float32))
    bias_added = tf.nn.bias_add(conv, biases)
    conv3 = tf.nn.relu(bias_added, name=scope.name)  # activate
print('conv3 layer ready')

# fully connected layers
with tf.variable_scope('fc1') as scope:
    fc_size = 1024
    # flatten dimensions except batch size
    dim = np.prod(conv3.get_shape().as_list()[1:])
    prev_layer_flat = tf.reshape(conv3, [-1, dim])  # vectorize

    weights = tf.get_variable('weights', [dim, fc_size])
    biases = tf.get_variable('biases', [fc_size])
    fc1_out = tf.nn.relu(tf.add(tf.matmul(prev_layer_flat, weights), biases))
    fc1_out_dr = tf.nn.dropout(fc1_out, keep_prob=0.7)
print('fully connected layer 1 ready')
fc_in = fc_size

with tf.variable_scope('fc2') as scope:
    fc_out = 512
    weights = tf.get_variable('weights', [fc_in, fc_out])
    biases = tf.get_variable('biases', [fc_out])
    fc2_out = tf.nn.relu(tf.add(tf.matmul(fc1_out_dr, weights), biases))
    fc2_out_dr = tf.nn.dropout(fc2_out, keep_prob=0.7)
print('fully connected layer 2 ready')
fc_in = fc_out

with tf.variable_scope('fc3') as scope:
    num_classes = 3
    weights = tf.get_variable('weights', [fc_in, num_classes])
    biases = tf.get_variable('biases', [num_classes])
    fc3_out = tf.add(tf.matmul(fc2_out_dr, weights), biases)  # no relu, no dropout
print('fully connected layer 3 ready')


# loss
cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
    logits=fc3_out, labels=y)
loss = tf.reduce_mean(cross_entropy)
tf.summary.scalar('loss', loss)  # save summary of loss

# optimize
# decayed_learning_rate = learning_rate * decay_rate ^ (global_step / decay_steps)
global_step = tf.Variable(0, trainable=False)
starter_learning_rate = 0.002
learning_rate = tf.train.exponential_decay(starter_learning_rate, global_step,
                                           decay_steps=500, decay_rate=0.50, staircase=True)
optimizer = tf.train.AdamOptimizer(learning_rate).minimize(loss, global_step=global_step)
tf.summary.scalar('learning_rate', learning_rate)
print('Optimizer Ready')

# evaluate
corrects = tf.equal(tf.argmax(fc3_out, axis=1), y)
accuracy = tf.reduce_mean(tf.cast(corrects, tf.float32))
tf.summary.scalar('accuracy', accuracy)  # save smmary of accuracy
print('Network ready!')

# create a saver to save the model
saver = tf.train.Saver()
print('Saver initialized')

# create a session
with tf.Session() as sess:
    # merge summaries and initialize writers
    merged = tf.summary.merge_all()  # merge summary
    train_writer = tf.summary.FileWriter('./summaries/train_ext', sess.graph)
    test_writer = tf.summary.FileWriter('./summaries//test_ext')
    print('Summary writers ready')

    # training
    print('Begin session')
    init = tf.global_variables_initializer()
    sess.run(init)

    # restoring model:
    # saver.restore(sess, './model/model.ckpt')
    # print('Model restored')

    for epoch in range(30):
        # refresh samples as new epoch begins
        sg = SampleGenerator(filename='augmented_dataset.h5', batch_size=15)
        sg.reset_index()
        print('epoch : {}'.format(epoch))

        # for batch iterations
        for batch_iter in range(sg.num_batches):
            batch_x, batch_y = sg.generate_sample_slices()
            summary, num_step, _ = sess.run([merged, global_step, optimizer],
                                            feed_dict={x: batch_x, y: batch_y})
            train_writer.add_summary(summary, num_step)

            # print intermediate results
            if batch_iter % 5 == 0:
                loss_val = sess.run(loss, feed_dict={x: batch_x, y: batch_y})
                print('loss : {}'.format(loss_val))
                train_acc = sess.run(accuracy, feed_dict={x: batch_x, y: batch_y})
                print('train acc : {}'.format(train_acc))
                test_x, test_y = sg.test_sample_slices()
                summary, test_acc, test_correct = sess.run([merged, accuracy, corrects],
                                                  feed_dict={x: test_x, y: test_y})
                test_writer.add_summary(summary, num_step)
                print('test_acc : {}'.format(test_acc))
                print('test_correct : {} / {}'.format(np.sum(test_correct),
                                                      len(test_correct)))
                print('')

    # save the trained model
    save_path = saver.save(sess, './model/model.ckpt')
    print('Model saved at : {}'.format(save_path))