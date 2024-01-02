"""
Usage:
  main.py <query>
  aggRelation use special ;, others use :
  jointreeEdge each edge use special |
"""
from treenode import *
from comparison import Comparison
from jointree import Edge, JoinTree
from aggregation import *
from generateIR import *
from generateAggIR import *
from generateTopKIR import *
from codegen import *
from codegenTopK import *


from random import randint
import os
import re
import traceback

GET_TREE = 'sparksql-plus-cli-jar-with-dependencies.jar'

BASE_PATH = 'query/topk1/'
DDL_NAME = 'graph.ddl'
QUERY_NAME = 'query.sql'
OUT_NAME = 'rewrite.txt'
REL_NAME = 'relations'
AGG_NAME = 'aggregations.txt'
TOPK_NAME = 'topK.txt'
JT_PATH = ''
OUT_PATH = 'outputVariables.txt'
AddiRelationNames = set(['TableAggRelation', 'AuxiliaryRelation', 'BagRelation']) #5, 5, 6


''' Formatt
RelationName;id;source/inalias(bag);cols;tableDisplayName;[AggList(tableagg)|internalRelations(bag)|supportingRelation(aux)|group+func(agg)]
Only AuxiliaryRelation source is [Bag(Graph,Graph)|Graph|...]
'''

def get_tree():
    cmdline = f'java -jar {GET_TREE} -d {BASE_PATH}{DDL_NAME} -o {BASE_PATH} {BASE_PATH}{QUERY_NAME}'
    out = os.popen(cmdline, mode='r').readlines()


def parse_ddl():
    try:
        f = open(BASE_PATH + DDL_NAME)
        table2vars = dict()
        line = f.readline()
        flag = 0
        tableName = ''
        cols = []
        while line:
            if 'TABLE' in line:         # begin attributes
                flag = 1
                line = line.split(' ')
                tableName = line[line.index('TABLE') + 1]
                cols.clear()
                line = f.readline()
                continue
            elif ';' in line: 
                flag = 2                # finish one table
                table2vars[tableName] = cols.copy()
                cols.clear()
                line = f.readline()
                continue
    
            if flag == 1:
                line = line.lstrip().rstrip().split(' ')[0]
                cols.append(line)
              
            line = f.readline()
    
        # TODO: Add PK-FK description
        return table2vars
    except FileNotFoundError:
        raise FileNotFoundError("DDL file not exist! ")


def parse_outVar():
    try :
        f = open(BASE_PATH + OUT_PATH)
        line = f.readline()
        flag = 0
        outputVariables = []
        isFull = True
        while line:
            if 'outputVariables:' in line  or 'isFull:' in line: 
                if 'outputVariables:' in line: flag = 1
                else: flag = 2
                line = f.readline()
                continue
            if flag == 1:
                name = line.split(':')[0]
                outputVariables.append(name)
            elif flag == 2:
                isFull = True if line == 'true' else False
            line = f.readline()
        return outputVariables, isFull
    except:
        get_tree()
        return parse_outVar()


def parse_agg():
    try:
        f = open(BASE_PATH + AGG_NAME)
        line = f.readline().rstrip()
        flag = 0
        outVars, aggFunc = [], []
        while line:
            if 'groupByVariables:' in line:
                flag = 1
                line = f.readline().rstrip()
                continue
            elif 'aggregations:' in line:
                flag = 2
                line = f.readline().rstrip()
                continue
        
            if flag == 1:
                outVars.append(line.split(':')[0])
            elif flag == 2:
                name, outName, inVars = line.split(';', 2)
                
                def parseVar(inVars: str):
                    formular = ''
                    if 'NULL' in inVars:
                        inVars = []
                    else:
                        formular = inVars.replace('AggList=|', '', 1)[:-2]
                        pattern = re.compile('v[0-9]+')
                        inVars = list(set(pattern.findall(inVars)))
                    return inVars, formular
                
                inVars, formular = parseVar(inVars)
                outName = outName.split(':')[0]
                agg = AggFunc(name, inVars, outName, formular)
                aggFunc.append(agg)
            
            line = f.readline().rstrip()
        
        Agg = Aggregation(outVars, aggFunc)
        return Agg
    except FileNotFoundError as e:
        return False
    except:
        traceback.print_exc()
    
    
def parse_topk() -> list[int, int, list[str], bool, int, GenType]:
    f = open(BASE_PATH + TOPK_NAME)
    line = f.readline().rstrip()
    # 0: levelk, 1: productk
    TopK = 0
    base = 32
    orderBy = ''    # use rating as default
    DESC, limit = line.split(',')[1:]
    DESC = True if DESC == 'true' else False
    limit = int(limit[:-1])
    genType = GenType.DuckDB
    return TopK, base, orderBy, DESC, limit, genType


def parseComparison(line: list[str]):
    id = int(line[0].split('=')[1])
    op = line[1].split('=')[1]
    left = line[2].split('=')[1]
    right = line[3].split('=')[1]
    path = line[4].split('=')[1].split(',')
    cond = line[5].split('=')[1][1:-1]
    fullOp = line[6].split('=')[1]
    return id, op, left, right, path, cond, fullOp


def parse_one_jt(allNodes: dict[id, TreeNode], isFull: bool, supId: set[int], jtPath: str):
    f = open(jtPath)
    line = f.readline().rstrip()
    flag = 0
    JT = JoinTree(allNodes, isFull, supId)
    CompareMap: dict[int, Comparison] = dict()
    
    while line:
        if 'jt.root:' in line  or 'edge:' in line  or 'relation in subset:' in line  or 'comparison hypergraph edge:' in line: 
            if 'jt.root:' in line: flag = 1    
            elif 'comparison hypergraph edge:' in line: flag = 4 
            elif 'edge:' in line: flag = 2      
            elif 'relation in subset:' in line and not isFull: flag = 3 
            else : flag = 5 # do nothing
            line = f.readline().rstrip()
            continue
        
        if flag == 1: # root
            line = int(line)
            JT.setRootById(line)
            
        elif flag == 2:
            rel1, rel2 = line.split('->')
            rel1, rel2 = int(rel1), int(rel2)
            edge = Edge(JT.getNode(rel1), JT.getNode(rel2))
            JT.addEdge(edge)
        
        elif flag == 3:
            line = int(line)
            JT.addSubset(line)
        
        elif flag == 4:
            line = line.split(';')[1:]
            id, op, left, right, path, cond, fullOp = parseComparison(line)
            Compare = Comparison()
            try:
                Compare.setAttr(id, op, left, right, path, cond, fullOp)
            except:
                traceback.print_exc()
                print(jtPath)
            leftAlias = JT.node[Compare.beginNodeId].cols
            # NOTE: fix left attrs not in beginNode, only happen in 2 table join
            pattern = re.compile('v[0-9]+')
            extractLeft = pattern.findall(Compare.left)
            if len(extractLeft) and extractLeft[0] not in leftAlias:
                Compare.reversePath()
            CompareMap[Compare.id] = Compare
            
        line = f.readline().rstrip()
        
    return JT, CompareMap


def parse_rel(id: str):
    f = open(BASE_PATH + REL_NAME + id + '.txt')
    line = f.readline().rstrip()
    allNodes = dict()   # Used for all nodes: id -> TreeNode
    seenId = set()      # Used for mark already processed Id
    
    supId = set()
    
    while line:
        line = line.split(';')
        name, id, source = line[0], int(line[1].split('=')[1]), line[2].split('=')[1]
        if id in seenId:
            line = f.readline().rstrip()
            continue
        else:
            seenId.add(id)
        cols = line[3].split('=')[1].replace('(', '').replace(')', '').split(',')
        cols = [col[:col.index(':')] for col in cols]
        alias = line[4].split('=')[1]
        if name == 'BagRelation':
            inAlias = source.split(',')
            inId = line[-1].split('=')[1].split(',')
            inId = [int(id) for id in inId]
            bagNode = BagTreeNode(id, source, cols, [], alias, inId, inAlias)
            allNodes[id] = bagNode
        
        elif name == 'AuxiliaryRelation':
            supportId = int(line[-1].split('=')[1])
            auxNode = AuxTreeNode(id, source, cols, [], alias, supportId)
            supId.add(supportId)
            allNodes[id] = auxNode
            
        elif name == 'TableScanRelation':
            tsNode = TableTreeNode(id, source, cols, [], alias)
            allNodes[id] = tsNode
            
        elif name == 'TableAggRelation':
            agglist = line[-1].split('=')[1].split(',')
            agglist = [int(agg) for agg in agglist]
            taNode = TableAggTreeNode(id, source, cols, [], alias, agglist)
            allNodes[id] = taNode
        
        elif name == 'AggregatedRelation':
            group = int(line[-2][line[-2].index('(')+1 : line[-2].index(')')])
            func = line[-1].split('=')[1]
            aNode = AggTreeNode(id, source, cols, [], alias, group, func)
            allNodes[id] = aNode
            
        else:
            raise NotImplementedError("Error relation name! ")
        
        line = f.readline().rstrip()
    
    return allNodes, supId


def parse_col2var(allNodes: dict[int, TreeNode], table2vars: dict[str, str]) -> dict[int, TreeNode]:
    sortedNodes = sorted(allNodes.items())
    ret = {k: v for k, v in sortedNodes}
    for id, treeNode in ret.items():
        # k: id, v: TreeNode
        vars = table2vars.get(treeNode.source, None) # Aux/bag can't get the corresponding
        if treeNode.relationType == RelationType.TableScanRelation:
            treeNode.setcol2vars([treeNode.cols, vars])
            
        elif treeNode.relationType == RelationType.AggregatedRelation:
            aggVars = [vars[treeNode.group], treeNode.func.name+'(*)']
            treeNode.setcol2vars([treeNode.cols, aggVars])
        
        elif treeNode.relationType == RelationType.TableAggRelation:    # tablescan+agg: source must in table2vars
            aggIds = treeNode.aggRelation
            aggAllVars = set()
            for id in aggIds:
                # NOTE: Only one aggregation function
                aggAllVars.add(allNodes[id].cols[-1])
            
            i = 0
            col2vars = [[], []]
            # 1. push original (not from aggList) first
            for col in treeNode.cols:
                if col not in aggAllVars:
                    col2vars[0].append(col)
                    col2vars[1].append(vars[i])
                    i += 1
            # 2. push agg values (alias tackle in aggNode)
            for var in aggAllVars:
                col2vars[0].append(var)
                col2vars[1].append('')
                
            treeNode.setcol2vars(col2vars)   
            
        elif treeNode.relationType == RelationType.BagRelation:
            allBagVars = set()
            allBagVarMap = dict()
            for eachId in treeNode.insideId:
                eachCols, eachVars = allNodes[eachId].col2vars
                eachAlias = allNodes[eachId].alias
                for index, eachCol in enumerate(eachCols):
                    if eachCol not in allBagVars:
                        allBagVars.add(eachCol)
                        allBagVarMap[eachCol] =  eachAlias + '.' + (eachVars[index] if allNodes[eachId].relationType == RelationType.TableScanRelation else eachCol)

            vars = [allBagVarMap[col] for col in treeNode.cols]
            treeNode.setcol2vars([treeNode.cols, vars])
            
        elif treeNode.relationType == RelationType.AuxiliaryRelation:
            supCols, supVars = allNodes[treeNode.supRelationId].col2vars
            auxCols, auxVars = [], []
            for index, col in enumerate(supCols):
                if col in treeNode.cols:
                    auxCols.append(col)
                    auxVars.append(supVars[index])
            treeNode.setcol2vars([auxCols, auxVars])
            
    return ret


'''Use JoinTree with minimum depth'''
def parse_jt(isFull: bool, table2vars: dict[str, str]):
    g = os.walk(BASE_PATH)
    optJT: JoinTree = None
    optCOMP: dict[int, Comparison] = None
    allRes = []
    
    for path,dir_list,file_list in g:
        for file_name in file_list:
            if 'JoinTree' in file_name:
                id = file_name.split('JoinTree')[1].split('.')[0]
                allNodes, supId = parse_rel(id)
                allNodes = parse_col2var(allNodes, table2vars)
                jt, comp = parse_one_jt(allNodes, isFull, supId, BASE_PATH + file_name)
                '''
                leafRelation = [rel.dst.id for rel in list(jt.edge.values()) if rel.dst.isLeaf]
                if jt.root.id in leafRelation:
                    continue    # not statidfied jointree, specific for one edge jointree
                '''
                if optJT is not None and jt.root.depth < optJT.root.depth:
                    optJT, optCOMP = jt, comp
                elif optJT is None:
                    optJT, optCOMP = jt, comp
                allRes.append([jt, comp, file_name])       

    return optJT, optCOMP, allRes


if __name__ == '__main__':
    path_ddl = ''
    table2vars = parse_ddl()
    outputVariables, isFull = parse_outVar()
    Agg = parse_agg()
    TopK, base, orderBy, DESC, limit, genType = parse_topk()
    IRmode = IRType.Report if not Agg else IRType.Aggregation
    IRmode = IRType.Level_K if TopK == 0 else IRmode
    IRmode = IRType.Product_K if TopK == 1 else IRmode
    optJT, optCOMP, allRes = parse_jt(isFull, table2vars)
    # sign for whether process all JT
    optFlag = False
    if optFlag:
        if IRmode == IRType.Report:
            reduceList, enumerateList, finalResult = generateIR(optJT, optCOMP, outputVariables)
            codeGen(reduceList, enumerateList, outputVariables, BASE_PATH + 'opt' +OUT_NAME, isFull=isFull)
        elif IRmode == IRType.Aggregation:
            aggList, reduceList, enumerateList, finalResult = generateAggIR(optJT, optCOMP, outputVariables, Agg)
            codeGen(reduceList, enumerateList, finalResult, outputVariables, BASE_PATH + 'opt' +OUT_NAME, aggGroupBy=Agg.groupByVars, aggList=aggList, isFull=isFull, isAgg=True)
        # NOTE: No comparison for TopK yet
        elif IRmode == IRType.Level_K:
            reduceList, enumerateList, finalResult = generateTopKIR(optJT, outputVariables, IRmode=IRType.Level_K, base=base, DESC=DESC, limit=limit)
            codeGenTopK(reduceList, enumerateList, finalResult,  BASE_PATH + 'opt' +OUT_NAME, IRmode=IRType.Level_K, genType=genType)
        elif IRmode == IRType.Product_K:
            reduceList, enumerateList, finalResult = generateTopKIR(optJT, outputVariables, IRmode=IRType.Product_K, base=base, DESC=DESC, limit=limit)
            codeGenTopK(reduceList, enumerateList, finalResult,  BASE_PATH + 'opt' +OUT_NAME, IRmode=IRType.Product_K, genType=genType)  
        
    else:
        for jt, comp, name in allRes:
            pattern = re.compile(r'\d+')
            index = pattern.findall(name)[0]
            outName = OUT_NAME.split('.')[0] + index + '.' + OUT_NAME.split('.')[1]
            try:
                if IRmode == IRType.Report:
                    reduceList, enumerateList, finalResult = generateIR(jt, comp, outputVariables)
                    codeGen(reduceList, enumerateList, finalResult, outputVariables, BASE_PATH + outName, isFull=isFull)
                elif IRmode == IRType.Aggregation:
                    Agg.initDoneFlag()
                    aggList, reduceList, enumerateList, finalResult = generateAggIR(jt, comp, outputVariables, Agg)
                    codeGen(reduceList, enumerateList, finalResult, outputVariables, BASE_PATH + outName, aggGroupBy=Agg.groupByVars, aggList=aggList, isFull=isFull, isAgg=True)
                # NOTE: No comparison for TopK yet
                elif IRmode == IRType.Level_K:
                    reduceList, enumerateList, finalResult = generateTopKIR(jt, outputVariables, IRmode=IRType.Level_K, base=base, DESC=DESC, limit=limit)
                    codeGenTopK(reduceList, enumerateList, finalResult, BASE_PATH + outName, IRmode=IRType.Level_K, genType=genType)
                elif IRmode == IRType.Product_K:
                    reduceList, enumerateList, finalResult = generateTopKIR(jt, outputVariables, IRmode=IRType.Product_K, base=base, DESC=DESC, limit=limit)
                    codeGenTopK(reduceList, enumerateList, finalResult, BASE_PATH + outName, IRmode=IRType.Product_K, genType=genType)

            except Exception as e:
                traceback.print_exc()
                print("Error JT: " + name)