# Proxmox Provisioning Reference

Create, clone, template, and delete VMs and LXC containers.

## Table of Contents

- [Create LXC Container](#create-lxc-container)
- [Create VM](#create-vm)
- [Clone VM/Container](#clone-vmcontainer)
- [Convert to Template](#convert-to-template)
- [Delete VM/Container](#delete-vmcontainer)
- [Available Templates & ISOs](#available-templates--isos)
- [Quick Reference](#quick-reference)

---

## Create LXC Container

```bash
# Get next available VMID
NEWID=$(curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/cluster/nextid" | jq -r '.data')

# Create container
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/lxc" \
  -d "vmid=$NEWID" \
  -d "hostname=my-container" \
  -d "ostemplate=local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst" \
  -d "storage=local-lvm" \
  -d "rootfs=local-lvm:8" \
  -d "memory=1024" \
  -d "swap=512" \
  -d "cores=2" \
  -d "net0=name=eth0,bridge=vmbr0,ip=dhcp" \
  -d "password=changeme123" \
  -d "start=1"
```

### LXC Parameters

| Param | Example | Description |
|-------|---------|-------------|
| vmid | 200 | Container ID |
| hostname | myct | Container hostname |
| ostemplate | local:vztmpl/debian-12-... | Template path |
| storage | local-lvm | Storage for rootfs |
| rootfs | local-lvm:8 | Root disk (8GB) |
| memory | 1024 | RAM in MB |
| swap | 512 | Swap in MB |
| cores | 2 | CPU cores |
| net0 | name=eth0,bridge=vmbr0,ip=dhcp | Network config |
| password | secret | Root password |
| ssh-public-keys | ssh-rsa ... | SSH keys (URL encoded) |
| unprivileged | 1 | Unprivileged container |
| start | 1 | Start after creation |

---

## Create VM

```bash
# Get next VMID
NEWID=$(curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/cluster/nextid" | jq -r '.data')

# Create VM
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu" \
  -d "vmid=$NEWID" \
  -d "name=my-vm" \
  -d "memory=2048" \
  -d "cores=2" \
  -d "sockets=1" \
  -d "cpu=host" \
  -d "net0=virtio,bridge=vmbr0" \
  -d "scsi0=local-lvm:32" \
  -d "scsihw=virtio-scsi-pci" \
  -d "ide2=local:iso/ubuntu-22.04.iso,media=cdrom" \
  -d "boot=order=scsi0;ide2;net0" \
  -d "ostype=l26"
```

### VM Parameters

| Param | Example | Description |
|-------|---------|-------------|
| vmid | 100 | VM ID |
| name | myvm | VM name |
| memory | 2048 | RAM in MB |
| cores | 2 | CPU cores per socket |
| sockets | 1 | CPU sockets |
| cpu | host | CPU type |
| net0 | virtio,bridge=vmbr0 | Network |
| scsi0 | local-lvm:32 | Disk (32GB) |
| ide2 | local:iso/file.iso,media=cdrom | ISO |
| ostype | l26 (Linux), win11 | OS type |
| boot | order=scsi0;ide2 | Boot order |

---

## Clone VM/Container

```bash
# Clone VM (full clone)
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/clone" \
  -d "newid=201" \
  -d "name=cloned-vm" \
  -d "full=1" \
  -d "storage=local-lvm"

# Clone LXC
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/lxc/{vmid}/clone" \
  -d "newid=202" \
  -d "hostname=cloned-ct" \
  -d "full=1" \
  -d "storage=local-lvm"
```

### Clone Parameters

| Param | Description |
|-------|-------------|
| newid | New VMID |
| name/hostname | New name |
| full | 1=full clone, 0=linked clone |
| storage | Target storage |
| target | Target node (for migration) |

---

## Convert to Template

```bash
# Convert VM to template (irreversible — VM must be stopped)
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}/template"

# Convert LXC to template
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/lxc/{vmid}/template"
```

---

## Delete VM/Container

```bash
# Delete VM (must be stopped first)
curl -ks -X DELETE -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}"

# Delete LXC
curl -ks -X DELETE -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/lxc/{vmid}"

# Force delete with disk cleanup
curl -ks -X DELETE -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu/{vmid}?purge=1&destroy-unreferenced-disks=1"
```

---

## Available Templates & ISOs

```bash
# List available LXC templates
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/storage/local/content?content=vztmpl" | jq '.data[] | .volid'

# List ISOs
curl -ks -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/storage/local/content?content=iso" | jq '.data[] | .volid'

# Download template from Proxmox appliance repo
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/aplinfo" \
  -d "storage=local" \
  -d "template=debian-12-standard_12.2-1_amd64.tar.zst"

# Restore from backup
curl -ks -X POST -H "$AUTH" "$PROXMOX_HOST/api2/json/nodes/{node}/qemu" \
  -d "vmid=300" \
  -d "archive=local:backup/vzdump-qemu-100-2024_01_01-12_00_00.vma.zst" \
  -d "storage=local-lvm"
```

---

## Quick Reference

| Action | Endpoint | Method |
|--------|----------|--------|
| Next ID | /cluster/nextid | GET |
| Create VM | /nodes/{node}/qemu | POST |
| Create LXC | /nodes/{node}/lxc | POST |
| Clone VM | /nodes/{node}/qemu/{vmid}/clone | POST |
| Clone LXC | /nodes/{node}/lxc/{vmid}/clone | POST |
| Template VM | /nodes/{node}/qemu/{vmid}/template | POST |
| Delete VM | /nodes/{node}/qemu/{vmid} | DELETE |
| Delete LXC | /nodes/{node}/lxc/{vmid} | DELETE |
| List templates | /nodes/{node}/storage/{s}/content?content=vztmpl | GET |
| List ISOs | /nodes/{node}/storage/{s}/content?content=iso | GET |
