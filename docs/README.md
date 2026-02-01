# Documentation

This directory contains documentation for the Satellite Migration Analysis Platform.

## Contents

### User Documentation

- **[USER_GUIDE.md](./USER_GUIDE.md)** - Complete user guide for the platform
  - Getting started
  - Feature guide (Animation Studio, Compare View, Export Center)
  - Available metrics reference
  - Troubleshooting

### Technical Documentation

- **[METHODOLOGY.md](./METHODOLOGY.md)** - Technical methodology documentation
  - Proxy metric definitions and formulas
  - Data processing pipeline
  - Temporal analysis methods
  - Validation approach
  - Limitations and caveats

- **[GEE_DATASETS.md](./GEE_DATASETS.md)** - GEE dataset integration guide
  - All 15 metrics with specifications
  - Colormaps and value ranges
  - Implementation architecture
  - Adding new metrics

### API Documentation

The API is self-documented via OpenAPI/Swagger:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Quick Links

| Topic | Document |
|-------|----------|
| How to use the platform | [USER_GUIDE.md](./USER_GUIDE.md) |
| Understanding the metrics | [METHODOLOGY.md](./METHODOLOGY.md) |
| GEE dataset details | [GEE_DATASETS.md](./GEE_DATASETS.md) |
| API endpoints | http://localhost:8000/docs |
| Source of Truth | [../SOT.md](../SOT.md) |

## Contributing

When adding documentation:
1. Use Markdown format
2. Include code examples where applicable
3. Keep language clear and concise
4. Update this README with new documents
