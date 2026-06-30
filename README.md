# travel reimbursement agent

reads a travel claim and decides: approve / partially approve / reject / manual review.

made for the genai assignment, its just a prototype.

## run it

```
pip install -r requirements.txt
cp .env.example .env        # put your cerebras key in here
python3 main.py --all
```

no key? it still runs, just uses the rules engine instead of the llm.

web ui: `python3 server.py` then open http://127.0.0.1:8000 (port 8000 cause mac took 5000)

tests: `python3 tests/test_tools.py`

## how it works

runs a few tools - check limits, check receipts, find duplicates, look up policy -
then the llm reads the results and gives the final decision as json.

sample claims are in data/claims.
