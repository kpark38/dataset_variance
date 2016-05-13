#!/usr/bin/env python

# Copyright 2014 Open Connectome Project (http://openconnecto.me)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# compute_metrics.py
# Created by Greg Kiar on 2016-05-11.
# Email: gkiar@jhu.edu

from argparse import ArgumentParser
from collections import OrderedDict
from subprocess import Popen

import numpy as np
import nibabel as nb
import networkx as nx
import os
import pickle


def loadGraphs(filenames, verb=False):
    """
    Given a list of files, returns a dictionary of graphs

    Required parameters:
        filenames:
            - List of filenames for graphs
    Optional parameters:
        verb:
            - Toggles verbose output statements
    """
    #  Initializes empty dictionary
    gstruct = OrderedDict()
    for idx, files in enumerate(filenames):
        if verb:
            print "Loading: " + files
        #  Adds graphs to dictionary with key being filename
        gstruct[files] = nx.read_graphml(files)
    return gstruct


def driver(names, fs, outdir, atlas, verb=False):
    """
    Given a set of files and a directory to put things, loads graphs and
    performs set of analyses on them, storing derivatives in a pickle format
    in the desired output location.

    Required parameters:
        names:
            - List of names of the datasets
        fs:
            - Dictionary of lists of files in each dataset
        outdir:
            - Path to derivative save location
        atlas:
            - Name of atlas of interest as it appears in the directory titles
    Optional parameters:
        verb:
            - Toggles verbose output statements
    """
    #  Loads graphs into memory for all datasets
    graphs = OrderedDict()
    for idx, name in enumerate(names):
        if verb:
            print "Loading Dataset: " + name
        # The key for the dictionary of graphs is the dataset name
        graphs[name] = loadGraphs(fs[name], verb=verb)

    """
    Now we start doing statistics...
    """

    #  Number of non-zero edges (i.e. binary edge count)
    nnz = OrderedDict()
    for idx, name in enumerate(names):
        nnz[name] = OrderedDict((subj, len(nx.edges(graphs[name][subj])))
                                for subj in graphs[name])
    write(outdir, 'nnz', nnz, atlas)

    #  Degree sequence
    deg = OrderedDict()
    for idx, name in enumerate(names):
        deg[name] = OrderedDict((subj, np.array(nx.degree(graphs[name][subj]).values()))
                                for subj in graphs[name])
    write(outdir, 'degree', deg, atlas)

    #  Edge Weights
    ew = OrderedDict()
    for idx, name in enumerate(names):
        ew[name] = OrderedDict((subj, [graphs[name][subj].get_edge_data(e[0], e[1])['weight']
                               for e in graphs[name][subj].edges()])
                               for subj in graphs[name])
    write(outdir, 'edgeweight', ew, atlas)

    #   Clustering Coefficients
    ccoefs = OrderedDict()
    for idx, name in enumerate(names):
        ccoefs[name] = OrderedDict((subj, nx.clustering(graphs[name][subj]).values())
                                   for subj in graphs[name])
    write(outdir, 'ccoefs', ccoefs, atlas)

    # Scan Statistic-1
    ss1 = OrderedDict()
    for idx, name in enumerate(names):
        ss1[name] = scan_statistic(graphs[name], 1)
    write(outdir, 'ss1', ss1, atlas)

    # Eigen Values
    laplacian = OrderedDict()
    eigs = OrderedDict()
    for idx, name in enumerate(names):
        laplacian[name] = OrderedDict((subj, nx.normalized_laplacian_matrix(graphs[name][subj]))
                                      for subj in graphs[name])
        eigs[name] = OrderedDict((subj, np.sort(np.linalg.eigvals(laplacian[name][subj].A))[::-1])
                                 for subj in graphs[name])
    write(outdir, 'eigs', eigs, atlas)

    # Betweenness Centrality
    centrality = OrderedDict()
    for idx, name in enumerate(names):
        centrality[name] = OrderedDict((subj, nx.algorithms.betweenness_centrality(graphs[name][subj]).values())
                                       for subj in graphs[name])
    write(outdir, 'centrality', centrality, atlas)


def scan_statistic(mygs, i):
    """
    Computes scan statistic-i on a set of graphs

    Required Parameters:
        mygs:
            - Dictionary of graphs
        i:
            - which scan statistic to compute
    """
    ss = OrderedDict()
    for key in mygs.keys():
        g = mygs[key]
        tmp = np.array(())
        for n in g.nodes():
            subgraph = nx.ego_graph(g, n, radius=i)
            tmp = np.append(tmp, np.sum([subgraph.get_edge_data(e[0], e[1])['weight']
                            for e in subgraph.edges()]))
        ss[key] = tmp
    return ss


def write(outdir, metric, data, atlas):
    """
    Write computed derivative to disk in a pickle file

    Required parameters:
        outdir:
            - Path to derivative save location
        metric:
            - The value that was calculated
        data:
            - The results of this calculation
        atlas:
            - Name of atlas of interest as it appears in the directory titles
    """
    of = open(outdir + '/' + atlas + '_' + metric + '.pkl', 'wb')
    pickle.dump({metric: data}, of)
    of.close()


def main():
    """
    Argument parser and directory crawler. Takes organization and atlas
    information and produces a dictionary of file lists based on datasets
    of interest and then passes it off for processing.

    Required parameters:
        atlas:
            - Name of atlas of interest as it appears in the directory titles
        basepath:
            - Basepath for which data can be found directly inwards from
        outdir:
            - Path to derivative save location
    Optional parameters:
        fmt:
            - Determines file organization; whether graphs are stored as
              .../atlas/dataset/graphs or .../dataset/atlas/graphs. If the
              latter, use the flag.
        verb:
            - Toggles verbose output statements
    """
    parser = ArgumentParser(description="Computes Graph Metrics")
    parser.add_argument("atlas", action="store", help="atlas directory to use")
    parser.add_argument("basepath", action="store", help="base directory loc")
    parser.add_argument("outdir", action="store", help="base directory loc")
    parser.add_argument("-f", "--fmt", action="store_true", help="Formatting \
                        flag. True if bc1, False if greg's laptop.")
    parser.add_argument("-v", "--verb", action="store_true", help="")
    result = parser.parse_args()

    #  Currently hardcoding the datasets I care about.
    #  GK TODO: Fix eventually
    dataset_names = list(('KKI2009', 'MRN114', 'MRN1313', 'SWU4',
                          'BNU1', 'BNU3', 'NKI1', 'NKIENH'))

    #  Sets up directory to crawl based on the system organization you're
    #  working on. Which organizations are pretty clear by the code, methinks..
    basepath = result.basepath
    atlas = result.atlas
    if result.fmt:
        dir_names = [basepath + '/' + d + '/' + atlas for d in dataset_names]
    else:
        dir_names = [basepath + '/' + atlas + '/' + d for d in dataset_names]

    #  Crawls directories and creates a dictionary entry of file names for each
    #  dataset which we plan to process.
    fs = OrderedDict()
    for idx, dd in enumerate(dataset_names):
        fs[dd] = [root + "/" + fl
                  for root, dirs, files in os.walk(dir_names[idx])
                  for fl in files if fl.endswith(".graphml")]

    print "Datasets: " + ", ".join([fkey + ' (' + str(len(fs[fkey])) + ')'
                                    for fkey in fs])

    p = Popen("mkdir -p " + result.outdir, shell=True)
    #  The fun begins and now we load our graphs and process them.
    driver(dataset_names, fs, result.outdir, atlas, result.verb)


if __name__ == "__main__":
    main()
