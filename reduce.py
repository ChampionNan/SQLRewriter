from action import Action
from enumsType import *
from comparison import *

class CreateBagView(Action):    
    # use joinTableList only, whereCondList is for connext internal 3 nodes
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str, joinTableList: list[str], whereCondList: list[str]) -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.joinTableList = joinTableList
        self.whereCondList = whereCondList
        self.reduceType = ReduceType.CreateBagView
    
    # TODO: later process how to join the internal tables
    def __repr__(self) -> str:
        return self.viewName + ' AS SELECT ' + str(self.selectAttrAlias) + ' AS ' + str(self.selectAttrs) + ' FROM ' + self.fromTable 


class CreateAuxView(Action):
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str) -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.reduceType = ReduceType.CreateAuxView
        
    # TODO: no cqc, just select out, only non-full, deal later; select all views from children? 
    def __repr__(self) -> str:
        return self.viewName + ' AS SELECT '


'''fromTable: tableScan, joinKeyList: a set of using()'''
'''Only matching selectAttrs is not '' need alias trans '''
class CreateTableAggView(Action):
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str, joinTableList: list[str], whereCondList: list[str]) -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.joinTableList = joinTableList 
        # self.joinKeyList = joinKeyList  # used for internal aggNode join
        self.whereCondList = whereCondList
        self.reduceType = ReduceType.CreateTableAggView
        
    def __repr__(self) -> str:
        return self.viewName + ' AS SELECT ' + str(self.selectAttrAlias) + ' AS ' + str(self.selectAttrs) + ' FROM ' + ', '.join(self.joinTableList) + ' WHERE ' + ' AND '.join(self.whereCondList)


class CreateOrderView(Action):
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str, joinKey: list[str], orderKey: list[str], AESC: bool) -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.joinKey = joinKey
        self.orderKey = orderKey
        self.AESC = AESC
        self.reduceType = ReduceType.CreateOrderView
        
    def __repr__(self) -> str:
        res = self.viewName + ' AS SELECT ' + str(self.selectAttrAlias) + ' AS ' + str(self.selectAttrs) + 'row_number()' + ' OVER (PARTITION BY ' + ', '.join(self.joinKey) + ' ORDER BY ' + self.orderKey
        res += ' DESC' if not self.AESC else '' 
        res += ') as rn FROM' + self.fromTable
        return res

class SelectMinAttr(Action):
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str, whereCond = "rn = 1") -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.whereCond = whereCond
        self.reduceType = ReduceType.SelectMinAttr
        
    def __repr__(self) -> str:
        return self.viewName + ' AS SELECT ' + str(self.selectAttrAlias) + ' AS ' + str(self.selectAttrs) + ' FROM ' + self.fromTable + ' WHERE ' + self.whereCond

'''
joinKey(using): used for same alias
joinCond(on): Some attributes don't have the same alias yet, but still put in where condition(empty use using joinKey)
whereCond: Use for mf1 < mf2
'''
class Join2tables(Action):
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str, joinTable: str, joinKey: list[str], joinCond: str = '', whereCond: str = '') -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.joinTable = joinTable
        self.joinKey = joinKey
        self.joinCond = joinCond
        self.whereCond = whereCond
        self.reduceType = ReduceType.Join2tables
        self._joinFlag = ' JOIN ' if len(self.joinKey) != 0 else ', '
        
    def __repr__(self) -> str:
        ret = self.viewName + ' AS SELECT ' + str(self.selectAttrAlias) + ' AS ' + str(self.selectAttrs) + ' FROM ' + self.fromTable + self._joinFlag + self.joinTable
        ret += 'using(' + ', '.join(self.joinKey) + ')' if self.joinCond == '' else ''
        ret += self.joinCond + self.whereCond
        return ret

# TODO: Add semijoin action
class SemiJoin(Action):
    def __init__(self, viewName: str, selectAttrs: list[str], selectAttrAlias: list[str], fromTable: str, joinTable: str, inLeft: list[str], inRight: list[str]) -> None:
        super().__init__(viewName, selectAttrs, selectAttrAlias, fromTable)
        self.joinTable = joinTable
        self.inLeft = inLeft
        self.inRight = inRight
        self.reduceType = ReduceType.CreateSemiJoinView
        self.semiFlag = 1

class ReducePhase:
    '''
    prepareView: child + parent(used for join)
    '''
    _reducePhaseId = 0
    def __init__(self, prepareView: list[Action], orderView: CreateOrderView, minView: SelectMinAttr, joinView: Join2tables, semiView: SemiJoin, corresNodeId: int, reduceDirection: Direction, phaseType: PhaseType, reduceOp: str, incidentComp: list[Comparison]) -> None:
        self.prepareView = prepareView
        self.orderView = orderView
        self.minView = minView
        self.joinView = joinView
        self.semiView = semiView
        self.reducePhaseId = ReducePhase._reducePhaseId
        self._addReducePhaseId
        self.corresNodeId: int = corresNodeId       # corresponds to nodeId in JoinTree
        self.reduceDirection: Direction = reduceDirection
        self.PhaseType = phaseType
        self.reduceOp = reduceOp
        self.incidentComp = incidentComp            # attach incident comparison

    @property
    def _addReducePhaseId(self):
        ReducePhase._reducePhaseId += 1

    def setPhaseType(self, type: PhaseType):
        self.PhaseType = type
        
    def __repr__(self) -> str:
        '[' + self.orderView.viewName + ', ' + self.minView.viewName + ', ' + self.joinView + ']'