# Siri Water Shortcut

Create a Shortcut named **Log Water** after the water API is deployed:

1. Add **Ask for Input**, choose **Number**, and use the prompt `How many milliliters?`.
2. Add **Get Contents of URL** with `https://personal.homehomehooray.com/api/water-entries`.
3. Set the method to **POST** and the request body to **JSON**.
4. Add the JSON field `amountMl` and set its value to **Provided Input**.
5. Add the header `X-Water-Log-Admin-Key` and set it to the Personal site's private key used by **Connect Siri & Sync**.
6. Get the `message` value from the response and add **Speak Text**.

Say “Siri, Log Water.” Siri will ask for the amount, save a timestamped entry to the KPI tracker, and speak the new logged total.

Keep the private key only in your Shortcut. Do not share the Shortcut publicly.
