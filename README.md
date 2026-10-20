New-Item -ItemType Directory -Force -Path "DockerImages"

docker images --format "{{.Repository}}:{{.Tag}}" |
Where-Object { $_ -ne "<none>:<none>" } |
ForEach-Object {
    $name = $_ -replace '[/ :]', '_'
    docker save -o "DockerImages\$name.tar" $_
} 




-------------

Get-ChildItem ".\DockerImages\*.tar" | ForEach-Object {
    docker load -i $_.FullName
}



docker network create dataplatform
docker compose -f .\elastic\elastic-docker-compose.yaml up -d
docker compose -f .\clickhouse\clickhouse-docker-compose.yaml up -d
docker compose -f .\deltalake\deltalake-docker-compose.yaml  up -d 

docker compose   .\trino_self_service_analytics\docker-compose.yml up --build