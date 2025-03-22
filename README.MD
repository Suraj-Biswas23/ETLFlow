## ETLFlow Data Flow Diagram (DFD)

```mermaid
graph TD;
    A[CSV File] -->|Upload| B[Data Processing];
    B -->|Extract Data| C[Data Transformation];
    C -->|Store in Database| D[MySQL Database];
    D -->|User Executes SQL Query| E[Query Engine];
    E -->|Processed Query Results| F[Data Visualization & Export];
    F -->|User Downloads| G[CSV / Parquet Export];
