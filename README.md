# 🚀 ETL Platform - Intelligent Data Cleaning

A modern, web-based ETL platform for automated data cleaning with AI-powered quality analysis and a plan-only LLM strategy.

## Features

✅ **Automatic Data Cleaning** - Remove duplicates, handle missing values, standardize types  
✅ **Data Profiling** - Analyze schemas and data quality  
✅ **AI Integration** - RAG + LLM plan suggestion, never direct data mutation  
✅ **CAG Engine** - Intelligent caching of LLM plans to reduce API costs by 60-80%  
✅ **Quality Reports** - Before/after analysis with improvement scores  
✅ **Multi-format Support** - CSV, Excel, JSON  
✅ **Export Options** - Download cleaned data in multiple formats  
✅ **Modern UI** - Responsive design with dark mode  

## Architecture

Dirty Data → Profiler → ML Column Role Detection → ML Anomaly Detection → RAG + LLM Plan Suggestion → Rules Engine Validation → Deterministic Transformation → Quality Check → Report

## Quick Start

### 1. Installation

\\\ash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
\\\

### 2. Run Backend

\\\ash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
\\\

Backend runs at: http://localhost:8000

### 3. Open Frontend

Open rontend/index.html in your browser

## Usage

1. Click "Lancer ETL" (Launch ETL)
2. Upload a CSV/Excel/JSON file
3. Wait for automatic processing
4. Review results and download cleaned data

## Project Structure

\\\
├── backend/              # FastAPI server
│   ├── main.py          # Main application
│   └── requirements.txt
├── frontend/            # Web interface
│   └── index.html
├── src/                 # Core modules
│   ├── extract.py       # Data extraction
│   ├── profiler.py      # Data profiling
│   ├── hybrid_ml.py     # Column roles, anomaly signals, action classification
│   ├── rag_engine.py    # RAG system
│   ├── llm_helper.py    # Plan generation and sanitization
│   ├── transform.py     # Data transformation
│   ├── rules_engine.py  # Deterministic execution of validated plans
│   ├── load.py          # Data export
│   └── utils.py         # Utilities
├── config/              # Configuration files
├── data/                # Data directories
├── reports/             # Generated reports
└── README.md
\\\

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /upload-and-process | POST | Process uploaded file |
| /export-csv | POST | Export as CSV |
| /export-excel | POST | Export as Excel |

## Technology Stack

- **Backend**: FastAPI, Pandas, Python
- **Frontend**: HTML5, CSS3, JavaScript
- **AI**: ChromaDB, LangChain
- **Database**: ChromaDB Vector Store

## Environment Variables

Create .env file (copy from .env.example):

\\\env
# Optional: For advanced RAG features
OPENAI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
\\\

## Development

### Running Tests

\\\ash
# Start backend
cd backend && python -m uvicorn main:app --reload

# Open frontend
open frontend/index.html
\\\

### Multi-Domain Strategy

See [reports/MULTI_DOMAIN_STRATEGY.md](reports/MULTI_DOMAIN_STRATEGY.md) for the recommended path to support logistics and sales use cases without fine-tuning too early.

### Adding Custom Plans

Extend `src/rag_engine.py` for knowledge-base hints, `src/hybrid_ml.py` for ML signals, and `src/llm_helper.py` to shape the final cleaning plan.

## Troubleshooting

**Backend won't start**
- Check Python version (3.8+)
- Run: pip install -r requirements.txt
- Verify port 8000 is available

**Upload fails**
- Ensure file format is CSV/Excel/JSON
- Check file isn't corrupted
- Try with smaller file first

**No results**
- Check backend logs for errors
- Verify CORS is enabled
- Clear browser cache

## License

MIT

## Version

1.0.0 - April 2026
