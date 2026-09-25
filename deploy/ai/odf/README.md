# OpenShift Data Foundation bucket

Apply this claim when the `openshift-storage.noobaa.io` storage class exists. The claim creates a Secret and ConfigMap with the bucket endpoint and keys. Copy those values into the `flyfish-s3` Secret and set `S3_ENDPOINT_URL` on the agents to that endpoint.

The default kustomization uses SeaweedFS in `flyfish-ai` so the demo does not require Data Foundation. Do not run both against the same bucket name without pointing the agents at one endpoint.
