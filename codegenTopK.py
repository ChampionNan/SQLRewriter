from codegen import transSelectData
from levelK import *
from productK import *
from enumsType import *

BEGIN = 'create or replace view '
DROP = 'drop table if exists '
END = ');\n'
BEGIN_TABLE = 'create table '
AS = ' as ('
MID = '), \n'
WITH = 'with '
WITHEND = ')\n'
VIEWEND = ');\n'

# BEGIN + ${name} + AS + WITH + ${name} + AS + ${select...} + WITHEND + ${select...} + MID + .. + VIEWEND
def genWithView(inView: WithView) -> str:
    line = 'select ' + transSelectData(inView.selectAttrs, inView.selectAttrAlias) + ' from ' + inView.fromTable
    if inView.joinTable:
        if len(inView.usingJoinKey):
            line += ' join ' + inView.joinTable + ' using(' + ','.join(inView.usingJoinKey) + ')'
        else:
            line += ', ' + inView.joinTable
    line += ' where ' if len(inView.whereCondList) else ''
    line += ' and '.join(inView.whereCondList)
    line += (' group by ' + ','.join(inView.groupBy)) if len(inView.groupBy) else ''
    line += (' order by ' + ','.join(inView.orderBy)) if len(inView.orderBy) else ''
    line += ' DESC' if inView.DESC else ''
    line += (' limit ' + str(inView.limit)) if inView.limit else ''
    
    return line


def genJoinUnionView(inView: EnumJoinUnion) -> str:
    line = 'select ' + transSelectData(inView.selectAttrs, inView.selectAttrAlias) + ' from ' + inView.fromTable
    if len(inView.usingJoinKey):
        line += ' join ' + inView.joinTable + ' using(' + ','.join(inView.usingJoinKey) + ')'
    else:
        line += ', ' + inView.joinTable
    line += ' where ' if len(inView.whereCondList) else ''
    line += ' and '.join(inView.whereCondList)
    line += (' group by ' + ','.join(inView.groupBy)) if len(inView.groupBy) else ''
    if inView.unionTable:
        line += ' union all ' + 'select * from ' + inView.unionTable
    line += (' order by ' + ','.join(inView.orderBy)) if len(inView.orderBy) else ''
    line += ' DESC' if inView.DESC else ''
    line += (' limit ' + str(inView.limit)) if inView.limit else ''
    
    return line

def genActionView(inView: Action):
    line = 'select ' + transSelectData(inView.selectAttrs, inView.selectAttrAlias) + ' from ' + inView.fromTable
    return line


def genRNView(inView: RNView):
    line = 'select ' + transSelectData(inView.selectAttrs, inView.selectAttrAlias) + ' from ' + inView.fromTable
    return line


def genSelectRNView(inView: EnumSelectRN):
    line = 'select ' + transSelectData(inView.selectAttrs, inView.selectAttrAlias) + ' from ' + inView.fromTable
    line += (' where ' + ' and '.join(inView.rnCond)) if len(inView.rnCond) else ''
    return line


def codeGenTopKLD(reduceList: list[LevelKReducePhase], enumerateList: list[LevelKEnumPhase], finalResult: str, outPath: str):
    outFile = open(outPath, 'w+')
    dropView, dropTable = [], []
    
    # 1. reduceList rewrite
    if len(reduceList):
        outFile.write('\n-- Reduce Phase: \n')
    for reduce in reduceList:
        outFile.write('\n-- Reduce' + str(reduce.levelKReducePhaseId) + '\n')
        line = BEGIN + reduce.orderView.viewName + AS + WITH + reduce.aggView.viewName + AS + genWithView(reduce.aggView) + WITHEND
        outFile.write(line)
        line = genWithView(reduce.orderView) + VIEWEND
        dropView.append(reduce.orderView.viewName)
        outFile.write(line)
    
    # 2. enumerateList rewrite
    for enum in enumerateList:
        outFile.write('\n-- Enumerate' + str(enum.levelKEnumPhaseId) + '\n')
        outFile.write('-- 0. rankView\n')
        line = BEGIN_TABLE + enum.rankView.finalView.viewName + AS + WITH + enum.rankView.maxView.viewName + AS + genWithView(enum.rankView.maxView) + MID
        outFile.write(line)
        line = enum.rankView.truncateView.viewName + AS + genWithView(enum.rankView.truncateView) + WITHEND
        outFile.write(line)
        line = genRNView(enum.rankView.finalView) + VIEWEND
        dropTable.append(enum.rankView.finalView.viewName)
        outFile.write(line)
        
        outFile.write('-- 1. logkLoop\n')
        line = BEGIN + enum.finalView.viewName + AS + WITH
        outFile.write(line)
        line = ''
        for index, loop in enumerate(enum.logkLoop):
            if loop.levelk_left:
                line = loop.levelk_left.viewName + AS + genSelectRNView(loop.levelk_left) + MID
            line += loop.levelk_right.viewName + AS + genSelectRNView(loop.levelk_right) + MID
            line += loop.levelk_join.viewName + AS + genJoinUnionView(loop.levelk_join)
            if index != len(enum.logkLoop) - 1: 
                line += MID
            else:
                line += WITHEND
            outFile.write(line)
        line = 'select ' + transSelectData(enum.finalView.selectAttrs, enum.finalView.selectAttrAlias) + ' from ' + enum.finalView.fromTable + VIEWEND
        outFile.write(line)
        dropView.append(enum.finalView.viewName)
        
    outFile.write(finalResult)
    if len(dropView):
        outFile.write('\n-- ')
        for table in reversed(dropView):
            line = 'drop view ' + table + ';'
            outFile.write(line)
    if len(dropTable):
        outFile.write('\n-- ')
        for table in reversed(dropTable):
            line = 'drop table ' + table + ';'
            outFile.write(line)
    outFile.close()
    
def codeGenTopKLM(reduceList: list[LevelKReducePhase], enumerateList: list[LevelKEnumPhase], finalResult: str, outPath: str):
    outFile = open(outPath, 'w+')
    dropView, dropTable = [], []
    
    # 1. reduceList rewrite
    if len(reduceList):
        outFile.write('\n# Reduce Phase: \n')
    for reduce in reduceList:
        outFile.write('\n## Reduce' + str(reduce.levelKReducePhaseId) + '\n')
        line = BEGIN + reduce.aggView.viewName + AS + genWithView(reduce.aggView) + END
        dropView.append(reduce.aggView.viewName)
        outFile.write(line)
        line = BEGIN + reduce.orderView.viewName + AS + genWithView(reduce.orderView) + END
        dropView.append(reduce.orderView.viewName)
        outFile.write(line)
    
    # 2. enumerateList rewrite
    if len(enumerateList):
        outFile.write('\n# Enumerate Phase: \n')
    for enum in enumerateList:
        outFile.write('\n## Enumerate' + str(enum.levelKEnumPhaseId) + '\n')
        outFile.write('## 0. rankView\n')
        line = BEGIN + enum.rankView.maxView.viewName + AS + genWithView(enum.rankView.maxView) + END
        outFile.write(line)
        dropView.append(enum.rankView.maxView.viewName)
        line = BEGIN_TABLE + enum.rankView.truncateView.viewName + AS + genWithView(enum.rankView.truncateView) + END
        outFile.write(line)
        dropTable.append(enum.rankView.truncateView.viewName)
        line = BEGIN + enum.rankView.finalView.viewName + AS + genRNView(enum.rankView.finalView) + END
        outFile.write(line)
        dropView.append(enum.rankView.finalView.viewName)
        
        outFile.write('## 1. logkLoop\n')
        for index, loop in enumerate(enum.logkLoop):
            if loop.levelk_left:
                line = BEGIN + loop.levelk_left.viewName + AS + genSelectRNView(loop.levelk_left) + END
                outFile.write(line)
                dropView.append(loop.levelk_left.viewName)
            
            line = BEGIN + loop.levelk_right.viewName + AS + genSelectRNView(loop.levelk_right) + END
            outFile.write(line)
            dropView.append(loop.levelk_right.viewName)
            line = BEGIN + loop.levelk_join.viewName + AS + genJoinUnionView(loop.levelk_join) + END
            outFile.write(line)
            dropView.append(loop.levelk_join.viewName)
        line = BEGIN + enum.finalView.viewName + AS + 'select ' + transSelectData(enum.finalView.selectAttrs, enum.finalView.selectAttrAlias) + ' from ' + enum.finalView.fromTable + END
        outFile.write(line)
        dropView.append(enum.finalView.viewName)
        
    outFile.write(finalResult)
    if len(dropView):
        line = '\n# drop view ' + ', '.join(reversed(dropView)) + ';'
        outFile.write(line)
    if len(dropTable):
        outFile.write('\n## ')
        for table in reversed(dropTable):
            line = 'drop table ' + table + ';'
            outFile.write(line)
    outFile.close()


def codeGenTopKPD(reduceList: list[ProductKReducePhase], enumerateList: list[ProductKEnumPhase], finalResult: str, outPath: str):
    outFile = open(outPath, 'w+')
    dropView = []
    
    # 1. reduceList rewrite
    outFile.write('with\n')
    for reduce in reduceList:
        if reduce.leafExtra:
            line = reduce.leafExtra.viewName + AS + genActionView(reduce.leafExtra) + MID
            outFile.write(line)
        line = reduce.aggMax.viewName + AS + genActionView(reduce.aggMax) + ' group by ' + ','.join(reduce.groupBy) + MID
        outFile.write(line)
        line = reduce.joinRes.viewName + AS + genWithView(reduce.joinRes) + MID
        outFile.write(line)
    
    # 2. enumerateList rewrite
    for index, enum in enumerate(enumerateList):
        line = enum.aggMax.viewName + AS + genActionView(enum.aggMax) + ' group by ' + ','.join(enum.groupBy) + MID
        outFile.write(line)
        line = enum.pruneJoin.viewName + AS + genWithView(enum.pruneJoin) + MID
        outFile.write(line)
        if index != len(enumerateList) - 1:
            line = enum.joinRes.viewName + AS + genWithView(enum.joinRes) + MID
        else:
            line = enum.joinRes.viewName + AS + genWithView(enum.joinRes) + WITHEND
        outFile.write(line)
    
    outFile.write(finalResult)
    outFile.close()
    
def codeGenTopKPM(reduceList: list[ProductKReducePhase], enumerateList: list[ProductKEnumPhase], finalResult: str, outPath: str):
    outFile = open(outPath, 'w+')
    dropView = []
    
    # 1. reduceList rewrite
    if len(reduceList):
        outFile.write('\n## Reduce Phase: \n')
    for reduce in reduceList:
        outFile.write('\n## Reduce' + str(reduce.productKReducePhaseId) + '\n')
        if reduce.leafExtra:
            outFile.write('## 0. leafExtra\n')
            line = BEGIN + reduce.leafExtra.viewName + AS + genActionView(reduce.leafExtra) + END
            outFile.write(line)
            dropView.append(reduce.leafExtra.viewName)
        outFile.write('## 1. aggMax\n')
        line = BEGIN + reduce.aggMax.viewName + AS + genActionView(reduce.aggMax) + ' group by ' + ','.join(reduce.groupBy) + END
        outFile.write(line)
        dropView.append(reduce.aggMax.viewName)
        outFile.write('## 2. joinRes\n')
        line = BEGIN + reduce.joinRes.viewName + AS + genWithView(reduce.joinRes) + END
        outFile.write(line)
        dropView.append(reduce.joinRes.viewName)
    
    # 2. enumerateList rewrite
    if len(enumerateList):
        outFile.write('\n## Enumerate Phase: \n')
    for index, enum in enumerate(enumerateList):
        outFile.write('\n## Enumerate' + str(enum.productKEnumPhaseId) + '\n')
        outFile.write('## 0. aggMax\n')
        line = BEGIN + enum.aggMax.viewName + AS + genActionView(enum.aggMax) + ' group by ' + ','.join(enum.groupBy) + END
        outFile.write(line)
        dropView.append(enum.aggMax.viewName)
        outFile.write('## 1. pruneJoin\n')
        line = BEGIN + enum.pruneJoin.viewName + AS + genWithView(enum.pruneJoin) + END
        outFile.write(line)
        dropView.append(enum.pruneJoin.viewName)
        outFile.write('## 2. joinRes\n')
        line = BEGIN + enum.joinRes.viewName + AS + genWithView(enum.joinRes) + END
        outFile.write(line)
        dropView.append(enum.joinRes.viewName)
    
    outFile.write(finalResult)
    if len(dropView):
        outFile.write('\n## ')
        line = 'drop view ' + ', '.join(dropView) + ';\n'
        outFile.write(line)

    outFile.close()


def codeGenTopK(reduceList, enumerateList, finalResult, outPath, IRmode: IRType = IRType.Level_K, genType: GenType = GenType.Mysql):
    if IRmode == IRType.Level_K and genType == GenType.Mysql:
        codeGenTopKLM(reduceList, enumerateList, finalResult, outPath)
    elif IRmode == IRType.Product_K and genType == GenType.Mysql:
        codeGenTopKPM(reduceList, enumerateList, finalResult, outPath)
    elif IRmode == IRType.Level_K and genType == GenType.DuckDB:
        codeGenTopKLD(reduceList, enumerateList, finalResult, outPath)
    elif IRmode == IRType.Product_K and genType == GenType.DuckDB:
        codeGenTopKPD(reduceList, enumerateList, finalResult, outPath)