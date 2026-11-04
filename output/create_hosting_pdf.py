from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, HRFlowable
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

OUT = Path(__file__).resolve().parent.parent / "output" / "pdf"
OUT.mkdir(parents=True, exist_ok=True)
PDF = OUT / "AGSuite_ERP_High_Scale_Hosting_Requirements_and_Cost_Comparison.pdf"

NAVY = colors.HexColor("#16324F")
BLUE = colors.HexColor("#1F5F8B")
PALE = colors.HexColor("#EEF4F8")
PALE2 = colors.HexColor("#F7FAFC")
INK = colors.HexColor("#1D2733")
MUTED = colors.HexColor("#596773")
BORDER = colors.HexColor("#CCD8E0")
GREEN = colors.HexColor("#176B4D")
ORANGE = colors.HexColor("#8A5518")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=31, textColor=NAVY, spaceAfter=9))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=12, leading=17, textColor=MUTED, spaceAfter=18))
styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=NAVY, spaceBefore=13, spaceAfter=7, keepWithNext=True))
styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=BLUE, spaceBefore=9, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle(name="Bulletx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.1, leading=12.8, leftIndent=12, firstLineIndent=-8, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle(name="Cellx", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10.1, textColor=INK))
styles.add(ParagraphStyle(name="CellHead", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.9, leading=10.2, textColor=colors.white))
styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.2, leading=14, textColor=GREEN, backColor=colors.HexColor("#EAF6F0"), borderColor=colors.HexColor("#A8D7BE"), borderWidth=.7, borderPadding=8, spaceBefore=5, spaceAfter=9))
styles.add(ParagraphStyle(name="CodeX", parent=styles["BodyText"], fontName="Courier", fontSize=7.4, leading=9.5, textColor=INK, backColor=colors.HexColor("#F3F5F7"), borderColor=BORDER, borderWidth=.4, borderPadding=7, spaceAfter=6))
styles.add(ParagraphStyle(name="Source", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.1, leading=9, textColor=MUTED, leftIndent=8, spaceAfter=3))

def P(text, style="Bodyx"):
    return Paragraph(text, styles[style])

def bullets(items):
    return [P("&#8226; " + x, "Bulletx") for x in items]

def table(headers, rows, widths, font=7.8):
    data = [[P(str(x), "CellHead") for x in headers]]
    for row in rows:
        data.append([P(str(x), "Cellx") for x in row])
    t = Table(data, colWidths=[w*mm for w in widths], repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("GRID", (0,0), (-1,-1), .45, BORDER),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0,i), (-1,i), PALE2))
    t.setStyle(TableStyle(commands))
    return t

def page_header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    if doc.page > 1:
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(.4)
        canvas.line(18*mm, height-14*mm, width-18*mm, height-14*mm)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(NAVY)
        canvas.drawString(18*mm, height-10.5*mm, "AGSuite ERP")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width-18*mm, height-10.5*mm, "High Scale Hosting Requirements and Cost Comparison")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(.4)
    canvas.line(18*mm, 13*mm, width-18*mm, 13*mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(18*mm, 8.5*mm, "Planning estimate - verify with provider calculators before purchase")
    canvas.drawRightString(width-18*mm, 8.5*mm, f"Page {doc.page}")
    canvas.restoreState()

story = []
story.append(Spacer(1, 25*mm))
story.append(P("AGSuite ERP", "CoverTitle"))
story.append(P("High Scale Hosting Requirements and Cost Comparison", "CoverTitle"))
story.append(P("Capacity target: 500 concurrent users, up to 5,000 PDFs in a burst, continuous Gmail/Zoho fetching, invoice extraction, validation, and NetSuite posting.", "CoverSub"))
story.append(HRFlowable(width="100%", thickness=1.3, color=BLUE, spaceBefore=5, spaceAfter=15))
story.append(P("Prepared for hosting and infrastructure planning", "H2x"))
story.append(P("Date: 4 November 2026<br/>Currency: USD per month, before taxes and provider-specific discounts<br/>Scope: application infrastructure only; AI/OCR API charges are shown separately.", "Bodyx"))
story.append(Spacer(1, 9*mm))
story.append(P("Executive decision", "H1x"))
story.append(P("The workload should be designed as an asynchronous, queue-based system. Five thousand PDFs do not require five thousand permanent servers: files enter a durable queue, a controlled worker pool processes them, and workers scale with queue depth. The exact cost depends on the completion-time target. A queue-friendly design can accept the burst at a much lower cost; a near-real-time design requires a large temporary worker fleet.", "Bodyx"))
story.append(P("Recommended starting production architecture: API service with 4-8 replicas, PostgreSQL primary with pooling, Redis/Key Value for queue and locks, 3-8 baseline OCR workers with autoscaling, 2-4 shared email/NetSuite workers, and persistent object/file storage. For a hard requirement that 5,000 PDFs complete within minutes, budget for 30-100 parallel OCR workers and load-test before committing.", "Callout"))
story.append(PageBreak())

story.append(P("1. Capacity assumptions", "H1x"))
story.append(P("The estimates below assume invoices are mostly PDF/image documents, extraction uses an external AI/OCR provider, and direct user uploads are asynchronous. They do not assume that all 5,000 PDFs must finish at the exact same instant; the completion target must be agreed before final sizing.", "Bodyx"))
story.append(table(["Workload", "Planning assumption", "Infrastructure consequence"], [
    ("Users", "500 concurrent authenticated users", "API is mostly I/O-bound; keep uploads and OCR out of request threads."),
    ("PDF burst", "Up to 5,000 PDFs accepted in a burst", "Durable queue, object/file persistence, backpressure, and autoscaling required."),
    ("Email", "1,000-2,000 messages continuously, 500-1,000 likely bills", "Mailbox polling, provider throttling, deduplication, retries, and shared integration workers."),
    ("NetSuite", "Validation and posting after extraction", "Idempotency keys, rate limiting, retry policy, and audit history."),
    ("Data", "Metadata, extracted JSON, history, logs, and file references", "Primary database with connection pooling; replicas only after measured read pressure."),
    ("Files", "Original PDFs/images and processed versions", "Persistent shared file storage; ephemeral service disks are not enough.")
], [29, 73, 78]))
story.append(P("The dominant cost is not the 500 users. It is the CPU/RAM required to process many documents in parallel, plus external AI/OCR calls and any provider API limits.", "Bodyx"))

story.append(P("2. Required production components", "H1x"))
story.append(table(["Component", "Recommended high-scale configuration", "Notes"], [
    ("Frontend", "Static site/CDN, 1 deployment", "React/Vite build; no server-side compute required."),
    ("API", "4-8 replicas, 2-4 vCPU and 4-8 GB RAM each", "Auth, upload metadata, status polling, review, integrations. Use connection pooling."),
    ("OCR workers", "3-8 baseline; autoscale to 30-100 for a short burst", "One document is one job; free workers take the next queued job. Size after measuring PDF time."),
    ("Email + NetSuite", "2-4 shared workers; scale to 4-8 for peak", "Separate queues, same worker service is acceptable. Use priority plus fairness."),
    ("Queue/cache", "Redis/Key Value 1-5 GB", "Job queue, locks, rate limiting, short-lived cache; PDFs should not be stored here."),
    ("Database", "PostgreSQL primary, 4-8 vCPU and 16-32 GB starting high-scale range", "Scale vertically first. Use pooling. Add read replica only when metrics justify it."),
    ("File storage", "Managed persistent object/file storage", "Keep original files out of service local disks."),
    ("Scheduler", "One active scheduler, optional standby", "Avoid two active schedulers creating duplicate mailbox jobs."),
    ("Observability", "Central logs, metrics, queue depth, tracing, error alerts", "Monitor processing time, retries, provider errors, DB connections, and storage.")
], [26, 72, 82]))
story.append(P("Design rule: API requests should enqueue work and return a job ID. OCR, email fetching, AI extraction, NetSuite validation, and posting must not depend on a long-running browser request.", "Callout"))

story.append(P("3. Worker and queue model", "H1x"))
story.append(P("The correct unit is a job, not a permanently dedicated worker. If 5 PDFs arrive and 3 OCR workers are free, three start immediately and two wait in the queue. When a worker finishes, it takes the next job. This lowers cost but increases completion time during bursts.", "Bodyx"))
story.append(table(["Queue", "Priority", "Concurrency policy", "Failure protection"], [
    ("NetSuite posting", "High but bounded", "Reserve capacity; never allow unlimited retries.", "Idempotency key, exponential backoff, provider rate limiter."),
    ("Email fetching", "Medium", "Keep polling responsive; do not let posting block mailbox checks.", "Cursor/state checkpoint, deduplication, reconnect handling."),
    ("OCR/extraction", "Normal", "Scale with queue depth and age; cap per-worker memory.", "Lease/recovery, retry limit, dead-letter status.")
], [30, 30, 58, 62]))
story.append(P("For 5,000 PDFs, agree an SLA such as: accept all within 5 minutes and complete within 60 minutes. Without this SLA, any worker count is only a guess.", "Bodyx"))

story.append(P("4. Cost scenarios", "H1x"))
story.append(P("These are planning ranges for the stated peak workload. They include application compute, database/queue, logging, and ordinary storage, but exclude AI/OCR token or page charges, email provider charges, NetSuite subscription charges, taxes, and enterprise support. High-scale estimates assume autoscaling rather than keeping the maximum fleet running all month.", "Bodyx"))
story.append(table(["Target", "OCR parallelism", "Meaning", "Expected infrastructure range"], [
    ("Queue-friendly", "3-10 workers", "5,000 PDFs accepted and processed over a longer window.", "$700-$2,500/month"),
    ("Production peak", "10-30 workers", "Good throughput with a queue during bursts; normal load scales down.", "$2,000-$7,000/month"),
    ("Near-real-time burst", "30-100 workers", "Designed to finish 5,000 PDFs within a tight window after load testing.", "$6,000-$20,000+/month")
], [32, 28, 80, 40]))
story.append(P("AI/OCR charges are separate. For example, if every invoice invokes a paid model or document OCR service, 5,000 documents can produce a large variable bill even when infrastructure is unchanged.", "Bodyx"))

story.append(PageBreak())
story.append(P("5. Render estimate", "H1x"))
story.append(P("Render is easy to operate because web services, private/background workers, Postgres, Key Value, autoscaling, TLS, and private networking are managed platform features. Render Pro is $25/month and enables autoscaling; compute is billed per service instance. Its published compute table lists 2 CPU/4 GB at $75/month and 4 CPU/16 GB at $200/month for service instances. Static sites are free.", "Bodyx"))
story.append(table(["Render service", "Suggested peak profile", "Planning quantity", "Approx. monthly"], [
    ("Static Site", "React/Vite", "1", "$0"),
    ("Web Service", "2 CPU / 4-8 GB", "4-8 replicas", "$300-$1,000"),
    ("OCR Background Worker", "4 CPU / 8-16 GB", "10-30 autoscaled", "$2,000-$12,000"),
    ("Email + NetSuite Worker", "2 CPU / 4 GB", "2-6", "$150-$900"),
    ("Postgres or external DB", "Managed primary + storage/backups", "1", "$200-$1,500+"),
    ("Key Value", "1-5 GB Redis-compatible", "1", "$30-$250"),
    ("Logs/bandwidth/disks", "Usage-dependent", "workspace", "$100-$800"),
    ("Workspace", "Pro for autoscaling", "1", "$25"),
    ("Total", "Peak-capable, excluding AI/OCR", "", "$2,800-$16,000+")
], [31, 67, 31, 51]))
story.append(P("Render is a good operational choice for the API and workers, but the 30-100 worker requirement can become expensive if the burst is sustained. Use autoscaling and queue age targets, not a permanently fixed maximum fleet.", "Bodyx"))
story.append(P("Official references: Render pricing and compute plans: https://render.com/pricing and https://render.com/docs/compute-plans", "Source"))

story.append(P("6. Railway estimate", "H1x"))
story.append(P("Railway uses a $20/month Pro subscription and usage-based billing. Published resource rates are $20 per vCPU-month, $10 per GB RAM-month, $0.05 per GB network egress, and $0.15 per GB-month volume storage. Pro allows up to 42 replicas, 1,000 vCPU, and 1 TB RAM across the plan, subject to platform limits.", "Bodyx"))
story.append(table(["Railway resource", "Peak planning assumption", "Approx. monthly"], [
    ("API replicas", "8 vCPU total, 16 GB RAM", "$320"),
    ("OCR workers", "40-120 vCPU and 80-240 GB RAM", "$1,600-$4,800"),
    ("Email + NetSuite", "8-16 vCPU and 16-32 GB RAM", "$320-$640"),
    ("Postgres/Redis services", "4-12 vCPU and 16-32 GB RAM", "$240-$560"),
    ("Volumes/egress", "Usage-dependent", "$100-$800"),
    ("Pro subscription", "1 workspace", "$20"),
    ("Total", "Peak-capable, excluding AI/OCR", "$2,600-$7,200")
], [42, 88, 50]))
story.append(P("Railway can be cheaper when workers scale down and usage is bursty, but it is usage-metered. Set hard usage limits and alerts before production; the platform can stop workloads when a configured limit is reached.", "Bodyx"))
story.append(P("Official references: Railway pricing plans and cost controls: https://docs.railway.com/pricing/plans and https://docs.railway.com/pricing/cost-control", "Source"))

story.append(P("7. Supabase estimate and role", "H1x"))
story.append(P("Supabase is best treated as the managed PostgreSQL/auth/storage data layer, not as the main OCR compute platform. Its Pro plan starts at $25/month and includes 8 GB database disk, 100 GB file storage, and 250 GB cached and uncached egress quotas. Extra compute, disk, backups, point-in-time recovery, replicas, file storage, and egress add to the bill.", "Bodyx"))
story.append(table(["Supabase component", "Recommended role", "Planning range"], [
    ("PostgreSQL primary", "Application data, extracted JSON, job state, audit history", "$25-$600+"),
    ("Connection pooler", "Protect DB from many API/worker connections", "Included/plan dependent"),
    ("Read replica", "Only after measured read bottleneck", "+$100-$800+"),
    ("Supabase Storage", "Possible file storage, but not currently configured in this project", "$25-$500+"),
    ("Egress/backups/PITR", "Depends on file traffic and retention", "$0-$1,000+"),
    ("Total data layer", "Primary only, before high egress", "$25-$1,500+")
], [42, 94, 44]))
story.append(P("For the current project, use one primary database first. A read replica increases cost and operational complexity; it is not a cost-saving measure. Keep documents out of PostgreSQL once durable file storage is selected.", "Bodyx"))
story.append(P("Official references: Supabase pricing and egress: https://supabase.com/pricing and https://supabase.com/docs/guides/platform/manage-your-usage/egress", "Source"))

story.append(PageBreak())
story.append(P("8. AWS estimate", "H1x"))
story.append(P("A production AWS design would normally use ECS/Fargate or EKS for API and worker tasks, RDS/Aurora PostgreSQL, ElastiCache Redis, S3 or another durable file store, Application Load Balancer, CloudWatch, IAM, Secrets Manager, and autoscaling. Fargate bills by requested vCPU, memory, storage, architecture, and task duration; RDS bills instance hours, storage, I/O, backups, and related networking.", "Bodyx"))
story.append(table(["AWS layer", "High-scale configuration", "Approx. monthly"], [
    ("ECS/Fargate API", "8-24 vCPU total, 16-48 GB RAM", "$500-$1,500"),
    ("ECS/Fargate OCR", "120-240 vCPU, 240-480 GB RAM at peak", "$5,000-$12,000"),
    ("Email/NetSuite tasks", "8-16 vCPU, 16-32 GB RAM", "$400-$900"),
    ("RDS PostgreSQL", "4-16 vCPU, 16-64 GB; Multi-AZ optional", "$400-$2,000"),
    ("ElastiCache Redis", "1-5 GB plus HA option", "$100-$600"),
    ("S3, ALB, logs, NAT, backups", "Usage and traffic dependent", "$300-$2,000"),
    ("Total", "Peak-capable, excluding AI/OCR", "$6,700-$19,000+")
], [42, 88, 50]))
story.append(P("AWS gives the strongest enterprise control and scaling options, but it also has the highest operations burden. ECS on EC2 or Graviton can reduce compute cost compared with always-on Fargate, at the cost of cluster management.", "Bodyx"))
story.append(P("Official references: AWS Fargate pricing: https://aws.amazon.com/fargate/pricing/; RDS billing: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/User_DBInstanceBilling.html; S3 pricing: https://aws.amazon.com/s3/pricing/", "Source"))

story.append(P("9. GCP estimate", "H1x"))
story.append(P("A GCP design would normally use Cloud Run for API and short-lived services, Cloud Run Jobs or GKE for long-running OCR workers, Cloud SQL for PostgreSQL, Memorystore for Redis, Cloud Storage for files, Cloud Load Balancing, Secret Manager, Cloud Logging, and autoscaling. Cloud Run is pay-per-use, but long-running high-concurrency OCR may fit GKE or Cloud Run Jobs better than request-bound processing.", "Bodyx"))
story.append(table(["GCP layer", "High-scale configuration", "Approx. monthly"], [
    ("Cloud Run API", "4-12 vCPU active capacity", "$250-$1,000"),
    ("Cloud Run Jobs/GKE OCR", "120-240 vCPU and 240-480 GB RAM at peak", "$4,500-$11,000"),
    ("Email/NetSuite services", "8-16 vCPU and 16-32 GB RAM", "$300-$900"),
    ("Cloud SQL PostgreSQL", "4-16 vCPU, 16-64 GB; HA optional", "$400-$2,200"),
    ("Memorystore Redis", "1-5 GB plus HA option", "$100-$700"),
    ("Cloud Storage, LB, logs, egress", "Usage dependent", "$300-$2,000"),
    ("Total", "Peak-capable, excluding AI/OCR", "$5,900-$17,800+")
], [42, 88, 50]))
story.append(P("GCP can be economical when workloads are bursty because Cloud Run meters CPU and memory by time used. For a 5,000-PDF hard SLA, test cold-start, concurrency, timeout, and CPU-allocation behavior before choosing Cloud Run alone.", "Bodyx"))
story.append(P("Official references: Cloud Run pricing: https://cloud.google.com/run/pricing; Cloud SQL pricing: https://cloud.google.com/sql/pricing; Cloud Storage pricing: https://cloud.google.com/storage/pricing", "Source"))

story.append(P("10. Recommended choice", "H1x"))
story.append(table(["Option", "Best fit", "Main risk", "Recommendation"], [
    ("Render", "Simplest managed deployment for API and workers", "Large OCR fleets can become expensive", "Good for first production if queue SLA is moderate."),
    ("Railway", "Usage-metered, simple multi-service deployment", "Bills rise with always-on peak workers; set limits", "Good for cost-sensitive teams with measured autoscaling."),
    ("Supabase + a compute platform", "Managed PostgreSQL plus separate API/worker hosting", "File storage/egress must be designed separately", "Recommended data layer; keep one primary initially."),
    ("AWS", "Enterprise control, HA, compliance, large scale", "Highest complexity and operations cost", "Best when enterprise controls justify the team/cost."),
    ("GCP", "Autoscaling and serverless-oriented workloads", "OCR execution model needs careful testing", "Good if the team is comfortable with Cloud Run/GKE.")
], [27, 59, 55, 39]))
story.append(P("Practical recommendation: start with Supabase PostgreSQL primary + Redis/Key Value + one compute provider for API and workers. Keep 3-8 OCR workers as the normal baseline, autoscale on queue depth and job age, and test a 5,000-PDF load before setting the maximum. Do not purchase the 30-100 worker fleet permanently unless the completion SLA requires it.", "Callout"))

story.append(P("11. Non-negotiable production requirements", "H1x"))
story.extend(bullets([
    "Durable queue with retry, lease/recovery, dead-letter status, and idempotency.",
    "Private persistent file storage with retention and backup policy.",
    "PostgreSQL connection pooling; separate read replica only when metrics justify it.",
    "Provider rate limiting for Gmail, Zoho, NetSuite, and AI services.",
    "Direct or resumable file upload path so API memory is not consumed by thousands of large files.",
    "Autoscaling based on queue length, oldest-job age, CPU, memory, and provider availability.",
    "Centralized logs and alerts for failed OCR, mailbox auth, NetSuite rejection, queue backlog, database health, and storage failures.",
    "Load tests for 500 authenticated users, 5,000 queued PDFs, 1,000 bill emails, duplicate delivery, retries, and provider throttling.",
    "Backups and a tested restore procedure for database, files, encryption keys, and configuration.",
    "Security controls: HTTPS, secure cookies, strict CORS/CSRF, secret manager, tenant authorization, private file access, and audit history."
]))
story.append(P("Final budgeting note", "H1x"))
story.append(P("For a manager-level budget, use $2,000-$7,000/month for a queue-optimized managed deployment, $6,000-$20,000+/month for a near-real-time 5,000-PDF peak, and add AI/OCR charges separately. AWS and GCP offer more control but can exceed these ranges once HA, networking, logs, replicas, and egress are included. These figures are planning bands, not provider quotes.", "Bodyx"))
story.append(P("Pricing references consulted", "H1x"))
story.append(P("Render: https://render.com/pricing<br/>Railway: https://docs.railway.com/pricing/plans<br/>Supabase: https://supabase.com/pricing<br/>AWS Fargate: https://aws.amazon.com/fargate/pricing/<br/>AWS S3: https://aws.amazon.com/s3/pricing/<br/>GCP Cloud Run: https://cloud.google.com/run/pricing<br/>GCP Cloud SQL: https://cloud.google.com/sql/pricing", "Source"))

doc = SimpleDocTemplate(str(PDF), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=20*mm, bottomMargin=18*mm, title="AGSuite ERP High Scale Hosting Requirements and Cost Comparison", author="AGSuite Technologies")
doc.build(story, onFirstPage=page_header_footer, onLaterPages=page_header_footer)
print(PDF)

