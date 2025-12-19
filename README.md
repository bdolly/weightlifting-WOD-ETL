# Weightlifting WOD ETL Pipeline

A serverless ETL pipeline built on AWS that extracts, transforms, and loads weightlifting workout data from the CrossFit Invictus WordPress blog into structured storage systems (DynamoDB and S3).

## Overview

This data engineering project implements an event-driven ETL pipeline that:

- **Extracts** workout posts from the Invictus WordPress API
- **Transforms** unstructured HTML content into structured workout sessions
- **Loads** processed data into DynamoDB (for querying) and S3 (for archival and analytics)

The pipeline is orchestrated using AWS Step Functions and runs on a scheduled basis via EventBridge.

## Architecture

### Technology Stack

- **Orchestration**: AWS Step Functions (State Machine)
- **Compute**: AWS Lambda (Python 3.8)
- **Storage**: 
  - Amazon S3 (raw data and processed weekly aggregates)
  - Amazon DynamoDB (structured session records)
- **Triggering**: Amazon EventBridge (scheduled)
- **Notifications**: Amazon SNS (SMS alerts)
- **Infrastructure as Code**: Serverless Framework

### ETL Pipeline Stages

The pipeline consists of 8 Lambda functions organized in a sequential processing flow:

1. **Extraction Layer**
   - `get_invictus_post`: Fetches latest posts from WordPress REST API

2. **Raw Data Storage**
   - `dump_post_to_bucket`: Persists raw JSON posts to S3 for audit trail

3. **Transformation Layer**
   - `strip_post_html`: Removes HTML markup using BeautifulSoup
   - `group_post_by_day`: Partitions content by weekday (Monday-Sunday)
   - `segment_days`: Segments each day into workout components (Session, Warm-Up, A., B., C., etc.)
   - `sessions_to_date_records`: Maps sessions to calendar dates
   - `clean_sessions_df_records`: Normalizes and cleans data using pandas

4. **Loading Layer**
   - `save_sessions_to_bucket`: Saves weekly aggregated data to S3 (JSON Lines format)
   - DynamoDB write: Parallel writes individual session records to DynamoDB

## Data Flow

```
EventBridge → Step Functions → Lambda Functions → Storage
     ↓              ↓                ↓              ↓
  Schedule    Orchestration    Processing    S3 + DynamoDB
```

### Detailed Flow

1. **Trigger**: EventBridge rule (10-minute schedule, currently disabled) or manual invocation
2. **Fetch**: `get_invictus_post` retrieves posts from WordPress API
3. **Map Processing** (Bronze → Silver): For each post:
   - **Bronze Layer**: Save raw JSON to S3 (`bronze/raw/{year}/{month}/{date}__{slug}__raw.json`)
   - Strip HTML to plain text
   - Group content by weekday
   - Segment into workout components
   - Convert to date-indexed records
   - Clean and normalize data
   - **Silver Layer**: Write cleaned sessions to S3 (`silver/sessions/{year}/week_{week}--{start_date}__{end_date}.jsonl`)
4. **Parallel Persistence**:
   - Write individual sessions to DynamoDB (partitioned by date, sorted by session)
   - Silver layer data saved to S3
5. **Gold Layer Aggregation**:
   - Create business-level aggregations from Silver layer
   - Save to S3 (`gold/aggregations/{year}/week_{week}--{start_date}__{end_date}.json`)
6. **Notification**: SNS sends structured SMS upon completion

## Data Schema

### DynamoDB Table Schema

**Table Name**: `invictus-weightlifting-sessions-{stage}`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `date` | String | Partition Key | ISO date format (YYYY-MM-DD) |
| `session` | String | Sort Key | Session identifier or "Rest Day" |
| `warm_up` | String | - | Warm-up instructions |
| `segment_a` | String | - | Workout segment A |
| `segment_b` | String | - | Workout segment B |
| `segment_c` | String | - | Workout segment C |
| `segment_d` | String | - | Workout segment D |
| `segment_e` | String | - | Workout segment E |

### S3 Data Structure (Medallion Architecture)

The pipeline uses a **Medallion Architecture** with three data layers:

```
s3://invictus-test-213/
├── bronze/                    # Bronze Layer: Raw data landing zone
│   └── raw/
│       └── {year}/
│           └── {month}/
│               └── {YYYY-MM-DD}__{slug}__raw.json
├── silver/                    # Silver Layer: Cleaned and validated data
│   └── sessions/
│       └── {year}/
│           └── week_{week}--{start_date}__{end_date}.jsonl
└── gold/                      # Gold Layer: Business aggregations
    └── aggregations/
        └── {year}/
            └── week_{week}--{start_date}__{end_date}.json
```

**Layer Details**:
- **Bronze**: Raw WordPress post JSON (immutable, partitioned by year/month)
- **Silver**: Cleaned session records in JSON Lines format (one record per line)
- **Gold**: Pre-computed weekly aggregations and business metrics

See `docs/MEDALLION_ARCHITECTURE.md` for detailed architecture documentation.

## Setup & Installation

### Prerequisites

- Node.js (v14+)
- Python 3.8+
- AWS CLI configured with appropriate credentials
- Serverless Framework CLI (`npm install -g serverless`)
- Docker (for Python package building on non-Linux systems)

### Environment Variables

Create a `.env` file in the project root:

```bash
INVICTUS_USER=your_wordpress_username
INVICTUS_PASS=your_wordpress_password
```

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd weightlifting-WOD-ETL
   ```

2. **Install Node.js dependencies**
   ```bash
   npm install
   ```

3. **Install Python dependencies** (optional, for local testing)
   
   Using uv (recommended, faster):
   ```bash
   uv pip install -r requirements.txt
   # Or use the lock file for reproducible installs
   uv pip install -r requirements.lock
   ```
   
   Using pip (traditional):
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure AWS credentials**
   ```bash
   aws configure --profile serverless-agent
   ```

## Deployment

### Deploy to AWS

```bash
# Deploy to dev stage (default)
serverless deploy

# Deploy to specific stage
serverless deploy --stage prod

# Deploy to specific region
serverless deploy --region us-west-2
```

### Deploy Individual Components

```bash
# Deploy only functions
serverless deploy function -f get_invictus_post

# Deploy only Step Functions
serverless deploy --step-functions-only
```

### Infrastructure Components Created

- 8 Lambda functions
- 1 Step Functions state machine
- 1 DynamoDB table
- 1 EventBridge rule (disabled by default)
- IAM roles and policies

## Configuration

### Serverless Configuration

Key configuration in `serverless.yml`:

- **Region**: `us-east-1`
- **Runtime**: `python3.8`
- **Stage**: `dev` (configurable via `--stage` flag)
- **S3 Bucket**: `invictus-test-213` (environment variable)
- **DynamoDB Table**: `invictus-weightlifting-sessions-{stage}`

### Step Functions Configuration

The state machine definition is in `SemiStructureInvictusPost_stateMachine.yml`:

- **State Machine Name**: `SemiStructureInvictusPostStateMachine`
- **Execution Model**: Standard (for long-running workflows)
- **Error Handling**: Built into Step Functions retry logic

### EventBridge Schedule

The EventBridge rule is **disabled by default**. To enable:

1. Update `serverless.yml` resources section:
   ```yaml
   State: ENABLED
   ```

2. Redeploy:
   ```bash
   serverless deploy
   ```

Or enable via AWS Console after deployment.

## Testing

### Local Testing

Test individual Lambda functions using the test events in `test_events/`:

```bash
# Test get_invictus_post
serverless invoke local -f get_invictus_post --path test_events/get_invictus_post.json

# Test transform functions
serverless invoke local -f group_post_by_day --path test_events/group_post_by_day.json
```

### Step Functions Testing

1. **Manual Execution via AWS Console**:
   - Navigate to Step Functions console
   - Select state machine
   - Click "Start execution"
   - Provide input JSON (see `test_events/` for examples)

2. **Programmatic Execution**:
   ```bash
   aws stepfunctions start-execution \
     --state-machine-arn <arn> \
     --input file://test_events/get_invictus_post.json
   ```

## Monitoring & Observability

### CloudWatch Logs

Each Lambda function logs to CloudWatch Logs:
- Log Group: `/aws/lambda/invictus-weightlifting-{stage}-{function-name}`

### X-Ray Tracing

X-Ray is enabled for distributed tracing across:
- Lambda functions
- Step Functions executions
- S3 operations
- DynamoDB operations

### Step Functions Execution History

View execution history in AWS Console:
- Execution status (Running, Succeeded, Failed)
- Input/output for each state
- Execution duration and costs
- Error details and retry attempts

## Data Engineering Patterns

### Extract Patterns

- **API Polling**: Scheduled extraction from WordPress REST API
- **Incremental Loading**: Fetches latest posts (configurable via `posts_per_page` and `page` parameters)
- **Raw Data Preservation**: All source data saved to S3 before transformation

### Transform Patterns

- **Text Processing**: HTML stripping, regex-based content segmentation
- **Data Normalization**: Pandas-based cleaning and standardization
- **Date Mapping**: Automatic date assignment based on week calculation
- **Schema Evolution**: Flexible JSON structure accommodates varying workout formats

### Load Patterns

- **Dual Write**: Parallel writes to both DynamoDB (operational) and S3 (analytical)
- **Partitioning**: S3 data partitioned by date ranges (weekly files)
- **Format Optimization**: JSON Lines format for efficient S3 Select queries
- **Idempotency**: Date + session composite key prevents duplicate writes

## Error Handling

### Lambda Error Handling

- Functions return error responses that Step Functions can handle
- Retry logic configured at Step Functions level
- Failed executions logged to CloudWatch

### Step Functions Error Handling

- Automatic retries with exponential backoff
- Error states captured in execution history
- Failed executions trigger SNS notifications

## Cost Optimization

- **Lambda**: Pay per invocation (128MB default memory)
- **Step Functions**: Standard workflow pricing
- **DynamoDB**: Provisioned capacity (1 read/write unit each)
- **S3**: Standard storage + request pricing
- **EventBridge**: Free tier includes 1M custom events/month

## Security

### IAM Permissions

Lambda execution role has minimal required permissions:
- S3 read/write to specific bucket
- DynamoDB CRUD on specific table
- Step Functions invocation
- SNS publish
- CloudWatch Logs write

### Secrets Management

- WordPress credentials stored as environment variables
- Consider migrating to AWS Secrets Manager for production

## Troubleshooting

### Common Issues

1. **Lambda Timeout**: Increase timeout in `serverless.yml` if processing large posts
2. **DynamoDB Throttling**: Increase provisioned capacity if experiencing throttling
3. **S3 Access Denied**: Verify bucket name and IAM permissions
4. **Step Functions Failure**: Check CloudWatch Logs for specific Lambda error details

### Debugging

```bash
# View Lambda logs
serverless logs -f get_invictus_post --tail

# View Step Functions execution
aws stepfunctions describe-execution --execution-arn <arn>

# Test S3 access
aws s3 ls s3://invictus-test-213/raw/ --profile serverless-agent
```

## Future Enhancements

- [ ] Add data validation layer (e.g., Great Expectations)
- [ ] Implement data quality checks
- [ ] Add data lineage tracking
- [ ] Migrate to EventBridge Scheduler (newer service)
- [ ] Add Glue Data Catalog for S3 data discovery
- [ ] Implement change data capture for updates
- [ ] Add data transformation versioning

## License

[Add license information]

## Contributing

[Add contributing guidelines]


