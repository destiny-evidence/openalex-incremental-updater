# Solr instance setup and management

This package contains a set of scripts to help you set up and manage a Solr instance. It is designed to be used with Solr 9.7.0.

A `cloud-init.yaml` file is provided to set up a Solr instance within an Azure VM. The script will install the necessary dependencies, configure the Solr instance, and start it. Some additional configuration is then required.

## Solr Setup on Azure VM

1. Create an Azure VM with Ubuntu 22.04 or your preferred long term support (LTS) version of Ubuntu. Other distributions will work, but instructions here are tailored for debian-based systems. Use the `cloud-init.yaml` file provided in this package to automate the setup process. You can use the Azure CLI or the Azure portal to create the VM and specify the `cloud-init.yaml` file during creation.
   - Ensure that the VM is _not_ publicly accessible. This is crucial for security reasons, as our Solr implementation does not have built-in authentication and authorization mechanisms. You can use a private IP address or a virtual network to restrict access to the VM. Since we're not planning on running a production instance, security is less of a focus than it would otherwise be. Our current running instance, for example, requires users to authenticate with `az login` and use `az ssh` to access the VM.
1. Ensure that the VM has sufficient resources. At least 8 GB of RAM and 2 CPUs are recommended for a basic Solr instance, though running queries and indexing large datasets may benefit from large amounts of RAM and CPU - in this case we used 64 GB of RAM, for example. Choose a SKU that fits your needs within Azure.
1. You'll need to obtain the PIK Solr configuration files from [the PIK GitHub repository](https://gitlab.pik-potsdam.de/mcc-apsis/nacsos/nacsos-academic-search/-/tree/main/openalex-ingest) and place them somewhere sensible on the VM.
1. Solr should be running as configured in the `cloud-init.yaml` file. You can check the status of Solr by running `sudo systemctl status solr` or by accessing the Solr admin interface at `http://<your-vm-ip>:8983/solr/`.
1. Stop Solr by running `sudo systemctl stop solr` and copy over the PIK Solr configuration files to the Solr configuration directory, typically located at `/var/solr/data/<collection_name>/conf/`. You'll want to edit the `/etc/systemd/system/solr.service` file (requires sudo) to match the content in the `config/solr.service` file provided in this package. This will ensure that Solr starts with the correct configuration. Solr will then expect data to be indexed in the `/var/solr/data/<collection_name>/data/` directory.
1. If you haven't already, copy the entire collection from blob storage to the Solr data directory. Authenticate via `az login` and `azcopy login` as usual, then run the following command to copy the collection from blob storage to the Solr data directory:

   ```bash
   azcopy copy "https://<your-storage-account-name>.blob.core.windows.net/<your-container-name>/<collection_name>/*" "/var/solr/data/<collection_name>/data/" --recursive
   ```

1. Edit the `/etc/default/solr.in.sh` file

   1. Set the `SOLR_JAVA_MEM` and `SOLR_OPTS` variables to suitable values for your VM. On the current running setup, with 8 vCPUs and 32 GB of RAM, we use

   ```sh
   SOLR_JAVA_MEM="-Xms16g -Xmx24g -XX:MaxDirectMemorySize=10g"
   SOLR_OPTS="$SOLR_OPTS -Dsolr.disableLuceneMMap=true"
   ```

   - We set the `SOLR_HOST` variable to `0.0.0.0` in the `/etc/default/solr.in.sh` file to allow Solr to listen on all interfaces. Crucially the VM should not be publicly accessible, reducing the risk of unauthorized access here.
   - Set `SOLR_MODULES=sql,clustering`
   - Set `SOLR_HOME=/var/solr`, `SOLR_PID_DIR=/var/solr/pid`, `SOLR_DATA_HOME=/var/solr/data`, `SOLR_LOGS_DIR=/var/solr/logs`, and `LOG4J_PROPS=/var/solr/log4j2.xml`.

1. Restart the Solr service by running `sudo systemctl restart solr`. You can check the status of Solr again with `sudo systemctl status solr` to ensure it is running correctly.
1. Update the `zookeeper` config with

   ```bash
   `/opt/solr/bin/solr zk upconfig -d nacsos-academic-search/openalex-ingest/setup/solr_configset/ -n _openalex_conf`
   ```

1. Create the collection with the following command:

   ```bash
   sudo /opt/solr/bin/solr create -c <collection_name> -n _openalex_conf
   ```

1. Restart the Solr service again with `sudo systemctl restart solr` to ensure all changes are applied.
1. You may see errors when importing the PIK Solr collection from blob storage. This is expected, and we spotted some errors in the index that can be fixed.

   - I removed the `openalex` collection from Solr with the command:

   ```bash
   sudo /opt/solr/bin/solr delete -c openalex
   ```

   - I created a new collection `openalex_replica` with the command:

   ```bash
   sudo /opt/solr/bin/solr create -c openalex_replica -n _openalex_conf
   ```

   - Index files were moved to `/var/solr/data/openalex_replica/data/index`
   - `segments_dim` references a missing index file, so `segments_dim` was removed from the index directory (and kept as a backup)
   - Run [Lucene's `CheckIndex` tool](https://lucene.apache.org/core/8_0_0/core/org/apache/lucene/index/CheckIndex.html) within the index directory to identify and fix any issues in the index:

   ```bash
   java -cp "/opt/solr-9.7.0/server/solr-webapp/webapp/WEB-INF/lib/*" org.apache.lucene.index.CheckIndex . -exorcise
   ```

1. Restart Solr and you should see that the collection is being populated.
