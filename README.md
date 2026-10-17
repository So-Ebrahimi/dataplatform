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