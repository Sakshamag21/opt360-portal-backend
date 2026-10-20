# Ways to Publish Events to Prometheus

Overview of 8 different methods to get Spark/job metrics into Prometheus, with trade-offs for each. Tailored to the operator360 setup: Spark Connect on K8s (data-platform namespace), metrics-proxy sidecar at port 9090, Prometheus Operator with CRDs.

---

## 1. PodMonitor / ServiceMonitor (Prometheus Operator CRD)

**Status:** 90% done — `spark-connect-monitor.yaml` already created, just not applied.

The standard Kubernetes-native way with Prometheus Operator. Define a `PodMonitor` CRD → Prometheus Operator auto-discovers it → Prometheus starts scraping the target.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: spark-connect-monitor
  namespace: data-platform
spec:
  podMetricsEndpoints:
    - port: metrics        # scrapes the sidecar at :9090
      path: /
  selector:
    matchLabels:
      app: spark-connect
```

**How to apply:**
```bash
kubectl apply -f spark-connect-monitor.yaml
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Pull |
| Custom metrics | Yes (via sidecar) |
| Effort | Low (just apply YAML) |
| Real-time | 15-30s scrape interval |
| Pros | Native to Prometheus Operator, auto-discovered, no code changes, supports label relabeling |
| Cons | Requires cluster access (`kubectl apply`), no local kubeconfig currently available |
| Best for | Current setup — already built, just needs one `kubectl apply` |

---

## 2. Prometheus Pushgateway (push model for batch jobs)

Designed for ephemeral/batch jobs that don't live long enough to be scraped. Spark jobs push metrics at completion.

**How it works:** Deploy a Pushgateway pod → Spark job pushes metrics via HTTP POST → Prometheus scrapes Pushgateway on a schedule.

```python
# In your scoring script, at job end:
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

registry = CollectorRegistry()
g = Gauge('spark_job_cpu_seconds', 'CPU time', ['feature'], registry=registry)
g.labels(feature='bio_mfc_fraud_score').set(12.5)
push_to_gateway('pushgateway.monitoring.svc:9091', job='opt360-scoring', registry=registry)
```

**Deploy Pushgateway:**
```bash
helm install pushgateway prometheus-community/prometheus-pushgateway -n monitoring
# Add a ServiceMonitor for Pushgateway itself
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Push |
| Custom metrics | Yes |
| Effort | Medium (deploy + code changes) |
| Real-time | At job end |
| Pros | Captures job-level metrics even after the pod/executor dies, works for sequential batch jobs |
| Cons | Pushgateway doesn't expire metrics automatically (stale data risk), needs separate deployment, push model (not Prometheus-native pull) |
| Best for | Batch job completion metrics |

---

## 3. Prometheus Remote Write (direct push to Prometheus)

Spark Connect server or sidecar pushes metrics directly to Prometheus's remote write API. No scraping needed.

**How it works:** Enable `--web.enable-remote-write-receiver` on Prometheus → sidecar POSTs metrics in Protobuf/JSON format.

```python
# In the sidecar, instead of exposing /metrics:
import requests
# Prometheus remote write protocol (Protobuf + Snappy)
# Or use the simpler JSON endpoint if available
requests.post('http://prometheus-k8s.gpu-monitoring.svc:9090/api/v1/write',
    data=snappy_compressed_protobuf_payload,
    headers={'X-Prometheus-Remote-Write-Version': '0.1.0'})
```

**Check if enabled:**
```bash
# Check Prometheus flags
kubectl exec -n gpu-monitoring prometheus-k8s-0 -- \
  prometheus --help 2>&1 | grep remote-write-receiver
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Push |
| Custom metrics | Yes |
| Effort | Medium (enable flag + code) |
| Real-time | Real-time |
| Pros | Real-time push (no scrape interval delay), works through firewalls, no PodMonitor needed |
| Cons | Requires `--enable-feature=remote-write-receiver` flag on Prometheus (may not be enabled), more complex payload encoding (Protobuf + Snappy), higher Prometheus load |
| Best for | When scraping isn't possible |

---

## 4. Spark's Built-in Prometheus MetricsSink

Spark has a native `MetricsSystem` with a Prometheus sink that exposes executor/driver metrics at `/metrics/executors/prometheus/`. This is what strot-spark's PodMonitor already scrapes.

**How it works:** Configure `metrics.properties` on the Spark Connect server → metrics exposed at a known HTTP path.

```properties
# $SPARK_HOME/conf/metrics.properties
*.sink.prometheus.class=org.apache.spark.metrics.sink.PrometheusSink
*.sink.prometheus.port=4041
*.sink.prometheus.path=/metrics/prometheus
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Pull |
| Custom metrics | No |
| Effort | Low (config only) |
| Real-time | 15-30s scrape |
| Pros | Built into Spark, no custom code, exposes JVM/executor/stage metrics |
| Cons | Doesn't include custom metrics (like `spark_job_executor_run_time`), bypasses your sidecar, only exposes Spark internals. This is why strot-spark's PodMonitor scrapes `/metrics/executors/prometheus/` but never sees your custom metric. |
| Best for | JVM/executor internals only |

---

## 5. JMX Exporter (Java agent)

Attach a JMX-to-Prometheus bridge as a Java agent to the Spark Connect JVM. Exposes all JMX MBeans as Prometheus metrics.

**How it works:** Download `jmx_prometheus_javaagent.jar` → add as `-javaagent` to Spark Connect server JVM → exposes metrics at a port.

```yaml
# In spark-connect3.yaml, modify the spark-connect-server container:
spec:
  containers:
    - name: spark-connect-server
      env:
        - name: JAVA_OPTS
          value: >-
            -javaagent:/opt/jmx_exporter/jmx_prometheus_javaagent-0.20.0.jar
            =9095:/opt/jmx_exporter/config.yml
      volumeMounts:
        - name: jmx-exporter
          mountPath: /opt/jmx_exporter
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Pull |
| Custom metrics | No |
| Effort | Medium (redeploy pod) |
| Real-time | 15-30s scrape |
| Pros | Rich JVM metrics (GC, memory pools, threads, Spark internals), battle-tested |
| Cons | Doesn't include custom per-job/per-feature metrics, needs config file, adds JVM overhead, needs redeployment of the Spark Connect pod |
| Best for | Deep JVM diagnostics |

---

## 6. OpenTelemetry Collector (modern observability stack)

Spark 3.4+ supports OpenTelemetry natively. Send metrics to an OTel Collector, which forwards to Prometheus.

**How it works:** Configure Spark's OTel sink → OTel Collector receives → exports to Prometheus via remote write.

```properties
# spark-defaults.conf
spark.metrics.conf.driver.source.jvm.class=org.apache.spark.metrics.source.JVMSource
spark.otel.collector.target=http://otel-collector.observability.svc:4317
```

```yaml
# OTel Collector pipeline
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
exporters:
  prometheusremotewrite:
    endpoint: http://prometheus-k8s.gpu-monitoring.svc:9090/api/v1/write
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Push |
| Custom metrics | Yes |
| Effort | High (deploy collector) |
| Real-time | Real-time |
| Pros | Vendor-neutral, supports traces + logs + metrics, future-proof, no scraping needed |
| Cons | Requires deploying OTel Collector (if not already present), Spark 3.4+ only (you have 4.0 so this works), more moving parts |
| Best for | Future-proof observability |

---

## 7. Custom Exporter (standalone polling service)

Write a small Python/Go service that polls the Spark REST API and exposes the results as Prometheus metrics. Deploy as a separate pod.

**How it works:** Exporter pod polls `http://spark-connect-service:4040/api/v1/applications/{id}/stages` every 15s → exposes as `/metrics` → Prometheus scrapes via ServiceMonitor.

```python
# exporter.py
from prometheus_client import start_http_server, Gauge
import requests, time

CPU_GAUGE = Gauge('spark_job_cpu_seconds', 'CPU time per feature', ['feature', 'job_id'])
MEM_GAUGE = Gauge('spark_job_peak_memory_bytes', 'Peak memory per feature', ['feature'])

def collect():
    apps = requests.get('http://spark-connect-service:4040/api/v1/applications').json()
    for app in apps:
        stages = requests.get(
            f'http://spark-connect-service:4040/api/v1/applications/{app["id"]}/stages'
        ).json()
        for stage in stages:
            for jid in stage.get('jobIds', []):
                feature = extract_tag(jid)
                CPU_GAUGE.labels(feature=feature, job_id=jid).set(
                    stage.get('executorCpuTime', 0) / 1000
                )

if __name__ == '__main__':
    start_http_server(8080)
    while True:
        collect()
        time.sleep(15)
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Pull |
| Custom metrics | Yes |
| Effort | Medium (write + deploy) |
| Real-time | 15s |
| Pros | Full control over what's exposed, can include business logic (per-feature attribution), doesn't modify Spark Connect pod, works with parallel execution |
| Cons | Extra pod to maintain, polling adds load, duplicates what your sidecar already does |
| Best for | Full control, business logic |

---

## 8. Grafana Alloy / Grafana Agent (scrape + forward)

Deploy Grafana Alloy (formerly Grafana Agent) as a sidecar or standalone pod that scrapes your sidecar and forwards to Prometheus via remote write.

**How it works:** Alloy scrapes `http://localhost:9090/` → forwards to Prometheus remote write endpoint.

```yaml
# alloy-config.yaml
metrics:
  wal_directory: /tmp/wal
  configs:
    - name: spark-connect
      scrape_configs:
        - job_name: spark-connect-sidecar
          static_configs:
            - targets: ['localhost:9090']
      remote_write:
        - url: http://prometheus-k8s.gpu-monitoring.svc:9090/api/v1/write
```

| Aspect | Detail |
|--------|--------|
| Push/Pull | Both |
| Custom metrics | Yes |
| Effort | Medium (deploy + config) |
| Real-time | Real-time |
| Pros | Handles scraping + forwarding, buffering if Prometheus is down, works without PodMonitor |
| Cons | Needs remote-write-receiver enabled on Prometheus, extra component, Alloy config to maintain |
| Best for | When PodMonitor can't be applied |

---

## Comparison Table

| # | Method | Push/Pull | Custom Metrics? | Effort | Real-time? | Best For |
|---|--------|-----------|-----------------|--------|------------|----------|
| 1 | **PodMonitor** | Pull | Yes (via sidecar) | Low (just apply YAML) | 15-30s scrape | Current setup |
| 2 | Pushgateway | Push | Yes | Medium (deploy + code) | At job end | Batch job completion metrics |
| 3 | Remote Write | Push | Yes | Medium (enable flag + code) | Real-time | When scraping isn't possible |
| 4 | Spark MetricsSink | Pull | No | Low (config only) | 15-30s | JVM/executor internals only |
| 5 | JMX Exporter | Pull | No | Medium (redeploy pod) | 15-30s | Deep JVM diagnostics |
| 6 | OpenTelemetry | Push | Yes | High (deploy collector) | Real-time | Future-proof observability |
| 7 | Custom Exporter | Pull | Yes | Medium (write + deploy) | 15s | Full control, business logic |
| 8 | Grafana Alloy | Both | Yes | Medium (deploy + config) | Real-time | When PodMonitor can't be applied |

---

## Recommendation For the operator360 Setup

Since the setup already has:
- A working metrics-proxy sidecar at port 9090
- A PodMonitor YAML file ready to apply (`spark-connect-monitor.yaml`)
- Prometheus Operator that watches the data-platform namespace

**Option 1 (PodMonitor)** is the clear winner — it's 90% done, just needs one `kubectl apply`. The only blocker is cluster access.

If cluster access isn't available soon, **Option 7 (Custom Exporter)** is the best fallback — can be deployed from within the Jupyter pod using the K8s API (which is already accessible), and it doesn't require touching the Spark Connect pod or applying CRDs.
