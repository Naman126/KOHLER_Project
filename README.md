# KOHLER AI BathPlanner
An interactive AI design assistant that converts natural-language constraints into automated, physically viable product bundle recommendations with procedural 3D visualization.

## Prerequisites
- Python 3.9+
- Streamlit

## Installation & Setup
1. Clone or extract the repository.
2. Navigate to the project root directory:
   `cd kohler-ai-bathplanner`
3. Create a virtual environment:
   `python -m venv .venv`
4. Activate the environment:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
5. Install dependencies:
   `pip install -r requirements.txt`

## Execution
Run the following command to launch the web application:
`streamlit run app.py`

The application will open automatically in your default browser at `http://localhost:8501`. 

## Testing the Prototype
Enter the following in the Natural Language input to test the 3D procedural generation and constraint engine:
> "I am designing an 8x8 foot square bathroom. My budget is Rs 4,00,000. I want a calming Japanese Zen style. Please include a smart toilet, a shower, a vanity, and a faucet. Prioritize water efficiency."
