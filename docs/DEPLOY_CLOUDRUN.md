# Cloud Run deployment status

The container recipe is suitable for running the keyless API prototype. Gemini and Earth Engine are not implemented, so deploying credentials does not activate those products.

Build and deploy after installing the Google Cloud CLI and configuring a project:

    gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/eyewall/eyewall
    gcloud run deploy eyewall --image REGION-docker.pkg.dev/PROJECT/eyewall/eyewall --region REGION --allow-unauthenticated

If a future server adapter needs GEMINI_API_KEY, store it in Secret Manager and bind the secret to the Cloud Run service at runtime. Never pass secrets as Docker build arguments or bake them into the image. Restrict public access if the review queue contains sensitive drafts.
