"""One-shot: reads the next N messages from processed_articles and prints them,
to confirm the ml-platform consumer's real output lands correctly post-cutover."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from confluent_kafka import Consumer  # noqa: E402

c = Consumer({
    "bootstrap.servers": "127.0.0.1:9092",
    "group.id": "verify-processed-articles",
    "auto.offset.reset": "earliest",
})
c.subscribe(["processed_articles"])

count = 0
new_batch = []
import time
deadline = time.time() + 15
while time.time() < deadline:
    msg = c.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        continue
    article = json.loads(msg.value())
    count += 1
    if article.get("processed_by") == "ml-platform":
        new_batch.append(article)

c.close()
print(f"total messages in topic (all history): {count}")
print(f"messages produced by the new ml-platform consumer: {len(new_batch)}\n")
for article in new_batch:
    print(f"title={article.get('title')!r} topic={article.get('topic')} "
          f"threat_score={article.get('threat_score')} risk_level={article.get('risk_level')}")
