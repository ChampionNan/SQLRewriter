select R.src as node1, S.src as node2, T.src as node3, T.dst as node4, R.rating+S.rating+T.rating as rating
from graph R, graph S, graph T
where R.dst = S.src and S.dst = T.src
order by rating desc
limit 128