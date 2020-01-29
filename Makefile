
SHELL = /bin/bash

package:
	docker build --tag cogeo-tiler:latest .
	docker run --name cogeo-tiler --volume $(shell pwd)/:/local -itd cogeo-tiler:latest bash
	docker exec -it cogeo-tiler bash '/local/bin/package.sh'
	docker stop cogeo-tiler
	docker rm cogeo-tiler
