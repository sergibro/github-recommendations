### Launch

In order to launch API Service run script `run.sh` as following:
`$ ./run.sh {X number for 800X port} [{number of workers} (default 8)]`

`number of workers` indicates how many parallel request for gunicorn can handle.

### Usage example

GET:

[http://localhost:8003/api/v1.0/get_closest_repos?gh_repo=https://github.com/apache/spark]()

Response:
```JSON
{
  "data": [
    {
      "distance": 0.0,
      "url": "apache/spark"
    },
    {
      "distance": 0.422,
      "url": "apache/kafka"
    },
    {
      "distance": 0.445,
      "url": "apache/storm"
    },
    {
      "distance": 0.46,
      "url": "apache/flink"
    },
    {
      "distance": 0.491,
      "url": "apache/hadoop"
    },
    {
      "distance": 0.522,
      "url": "apache/hbase"
    },
    {
      "distance": 0.548,
      "url": "databricks/learning-spark"
    },
    {
      "distance": 0.564,
      "url": "neo4j/neo4j"
    },
    {
      "distance": 0.566,
      "url": "akka/akka"
    },
    {
      "distance": 0.571,
      "url": "apache/lucene-solr"
    }
  ],
  "exists": true,
  "query": "https://github.com/apache/spark",
  "repo_query": "apache/spark",
  "top_n": 10
} 
```
