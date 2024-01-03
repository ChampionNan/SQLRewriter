select R.src as node1, S.src as node2, S.dst as node3, R.rating + S.rating as rating
from graph R, graph S
where R.dst = S.src
order by rating desc
limit 128
