
Please review the new code that was added into @parser/ this is an open source contribution that is incomplete. It is intended to be incorporated within our app, potentially in a new page called "Pricer". It should replicate the basic behavior of Janice https://janice.e-351.com/ However, it only needs to provide the basic pricing functionality to retrieve Jita market prices with the addition of 4-HWWF. 

- Data for Jita should be available from Janice directly (using the API key in @.streamlit/secrets.toml), Fuzzworks, or the ESI directly. 
- Data for 4-HWWF can be found in our local market database. 

## Metrics for Success
- User should be able to paste in tab separated list of items with the first two columns of either:
  item  quantity 
  quantity item
- an arbitrary number of additional columns may be included and ignored. 
- the tool should also be able to parse an EFT formatted Eve online ship fit. 
- The Pricer tool should also be capable of successfully parsing a EFT fitting file for an Eve Online ship when pasted by the user. You can find an example EFT fit in the @parser directory of this repository and review documentation for it here: https://developers.eveonline.com/docs/guides/fitting/
- The Pricer tool may use streamlit native features to replicate the Janice functionality.

Sample data for item lists users may paste into the pricer is also included in pricer/items.txt





