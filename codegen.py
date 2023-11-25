from enumerate import *
from reduce import *
from enumsType import *

BEGIN = 'create or replace view '
END = ';\n'

def transSelectData(selectAttrs: list[str], selectAttrAlias: list[str], row_numer: bool = False, max_rn: bool = False) -> str:
    extraAdd = (', row_number()' if row_numer else '') + (', max(rn) as mrn' if max_rn else '')
    if len(selectAttrs) == 0: return ', '.join(selectAttrAlias) + extraAdd
    if len(selectAttrs) != len(selectAttrAlias):
        raise RuntimeError("Two sides are not equal! ") 
    
    selectData = []
    for index, alias in enumerate(selectAttrAlias):
        if selectAttrAlias[index] == '': continue
        if selectAttrs[index] != '':
            selectData.append(selectAttrs[index] + ' as ' + selectAttrAlias[index])
        else:
            selectData.append(selectAttrAlias[index])
            
    ret = ', '.join(selectData) + extraAdd
    return ret

def codeGen(reduceList: list[ReducePhase], enumerateList: list[EnumeratePhase], outputVariables: list[str], outPath: str, isFull = True):
    outFile = open(outPath, 'w+')
    dropView = []
    # 1. reduceList rewrite
    outFile.write('## Reduce Phase: \n')
    for reduce in reduceList:
        outFile.write('\n# Reduce' + str(reduce.reducePhaseId) + '\n')
        
        if len(reduce.prepareView) != 0:
            outFile.write('# 0. Prepare\n')
            for prepare in reduce.prepareView:
                if prepare.reduceType == ReduceType.CreateBagView:
                    line = BEGIN + prepare.viewName + ' as select ' + transSelectData(prepare.selectAttrs, prepare.selectAttrAlias) + ' from ' + ', '.join(prepare.joinTableList) + ' where ' + ' and '.join(prepare.whereCondList) + END
                elif prepare.reduceType == ReduceType.CreateAuxView:
                    line = BEGIN + prepare.viewName + ' as select ' + transSelectData(prepare.selectAttrs, prepare.selectAttrAlias) + ' from ' + prepare.fromTable + END
                else:   # TableAgg
                    line = BEGIN + prepare.viewName + ' as select ' + transSelectData(prepare.selectAttrs, prepare.selectAttrAlias) + ' from ' + prepare.fromTable + ', ' + ', '.join(prepare.joinTableList) + ' where ' + ' and '.join(prepare.whereCondList) + END
                
                dropView.append(prepare.viewName)
                outFile.write(line)
        
        if reduce.semiView is not None:
            outFile.write('# +. SemiJoin\n')
            line = BEGIN + reduce.semiView.viewName + ' as select ' + transSelectData(reduce.semiView.selectAttrs, reduce.semiView.selectAttrAlias) + ' from ' + reduce.semiView.fromTable + ' where (' + ', '.join(reduce.semiView.inLeft) + ') in (select ' + ', '.join(reduce.semiView.inRight) + ' from ' + reduce.semiView.joinTable + ')' + END
            outFile.write(line)
            dropView.append(reduce.semiView.viewName)
            continue
                
        # CQC part, if orderView is None, pass do nothing (for aux support relation output case)
        if reduce.orderView is not None:    
            
            outFile.write('# 1. orderView\n')
            line = BEGIN + reduce.orderView.viewName + ' as select ' + transSelectData(reduce.orderView.selectAttrs, reduce.orderView.selectAttrAlias, row_numer=True) + ' over (partition by ' + ', '.join(reduce.orderView.joinKey) + ' order by ' + ', '.join(reduce.orderView.orderKey) + (' DESC' if not reduce.orderView.AESC else '') + ') as rn ' + 'from ' + reduce.orderView.fromTable + END
            dropView.append(reduce.orderView.viewName)
            outFile.write(line)
            outFile.write('# 2. minView\n')
            line = BEGIN + reduce.minView.viewName + ' as select ' + transSelectData(reduce.minView.selectAttrs, reduce.minView.selectAttrAlias) + ' from ' + reduce.minView.fromTable + ' where ' + reduce.minView.whereCond + END
            dropView.append(reduce.minView.viewName)
            outFile.write(line)
            outFile.write('# 3. joinView\n')
            line = BEGIN + reduce.joinView.viewName + ' as select ' + transSelectData(reduce.joinView.selectAttrs, reduce.joinView.selectAttrAlias) + ' from '
            joinSentence = reduce.joinView.fromTable
            if reduce.joinView._joinFlag == ' JOIN ':
                joinSentence +=' join ' + reduce.joinView.joinTable + ' using(' + ', '.join(reduce.joinView.alterJoinKey) + ')'
            else:
                joinSentence += ', ' + reduce.joinView.joinTable
            whereSentence = reduce.joinView.joinCond + (' and ' if reduce.joinView.joinCond != '' and reduce.joinView.whereCond else '') + reduce.joinView.whereCond
            line += joinSentence + ((' where ' + whereSentence) if whereSentence != '' else '') + END
            dropView.append(reduce.joinView.viewName)
            outFile.write(line)
    
    # 2. enumerateList rewrite
    outFile.write('\n## Enumerate Phase: \n')
    for enum in enumerateList:
        outFile.write('\n# Enumerate' + str(enum.enumeratePhaseId) + '\n')
        if enum.semiEnumerate is not None:
            outFile.write('# +. SemiEnumerate\n')
            line = BEGIN + enum.semiEnumerate.viewName + ' as select ' + transSelectData(enum.semiEnumerate.selectAttrs, enum.semiEnumerate.selectAttrAlias) + ' from ' + enum.semiEnumerate.fromTable
            line += ' join ' if len(enum.semiEnumerate.joinKey) != 0 else ', '
            line += enum.semiEnumerate.joinTable
            line += ' using(' + ', '.join(enum.semiEnumerate.joinKey) + ')' if len(enum.semiEnumerate.joinKey) != 0 else ''
            line += ' where ' + enum.semiEnumerate.joinCond if enum.semiEnumerate.joinCond != '' else ''
            line += END
            outFile.write(line)
            dropView.append(enum.semiEnumerate.viewName)
            continue
        
        outFile.write('# 1. createSample\n')
        line = BEGIN + enum.createSample.viewName + ' as select ' + enum.createSample.selectAttrAlias[0] + ' from ' + enum.createSample.fromTable + ' where ' + enum.createSample.whereCond + END
        dropView.append(enum.createSample.viewName)
        outFile.write(line)
        
        outFile.write('# 2. selectMax\n')
        line = BEGIN + enum.selectMax.viewName + ' as select ' + transSelectData(enum.selectMax.selectAttrs, enum.selectMax.selectAttrAlias, row_numer=False, max_rn=True) + ' from ' + enum.selectMax.fromTable + ' join ' + enum.selectMax.joinTable + ' using(' + ', '.join(enum.selectMax.joinKey) + ') where ' + enum.selectMax.whereCond + ' group by ' + ', '.join(enum.selectMax.groupCond) + END 
        dropView.append(enum.selectMax.viewName)
        outFile.write(line)
        
        outFile.write('# 3. selectTarget\n')
        line = BEGIN + enum.selectTarget.viewName + ' as select ' + ', '.join(enum.selectTarget.selectAttrAlias) + ' from ' + enum.selectTarget.fromTable + ' join ' + enum.selectTarget.joinTable + ' using(' + ', '.join(enum.selectTarget.joinKey) + ')' + ' where ' + enum.selectTarget.whereCond + END
        dropView.append(enum.selectTarget.viewName)
        outFile.write(line)
        
        outFile.write('# 4. stageEnd\n')
        line = BEGIN + enum.stageEnd.viewName + ' as select ' + ', '.join(enum.stageEnd.selectAttrAlias) + ' from ' + enum.stageEnd.fromTable + ' join ' + enum.stageEnd.joinTable + ' using(' + ', '.join(enum.stageEnd.joinKey) + ')' + ' where ' + enum.stageEnd.whereCond + END
        dropView.append(enum.stageEnd.viewName)
        outFile.write(line)
        
    if len(enumerateList) == 0:
        fromTable = reduce.joinView.viewName if reduce.joinView else reduce.semiView.viewName
        line = 'select count(' + ('distinct ' if not isFull else '') + ', '.join(outputVariables) +') from ' + fromTable + END
    else:
        fromTable = enum.stageEnd.viewName if enum.stageEnd else enum.semiEnumerate.viewName
        line = 'select count(' + ('distinct ' if not isFull else '') + ', '.join(outputVariables) +') from ' + fromTable + END
    outFile.write(line)
    
    line = '\n# drop view ' + ', '.join(dropView) + END
    outFile.write(line)
    
    outFile.close()
    