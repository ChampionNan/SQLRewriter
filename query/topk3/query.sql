select R.src as node1, S.src as node2, T.src as node3, U.src as node4, U.dst as node5, R.rating+S.rating+T.rating+U.rating as total_rating
from graph R, graph S, graph T, graph U
where R.dst = S.src and S.dst = T.src and T.dst = U.src
order by total_rating desc
limit 128
