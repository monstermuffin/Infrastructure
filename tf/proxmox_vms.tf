locals {
  proxmox_inventory_group_vars = yamldecode(file("${path.module}/../ansible/inventory/group_vars/all.yml"))
  proxmox_inventory_hosts      = yamldecode(file("${path.module}/../ansible/inventory/proxmox.yml"))

  proxmox_vm_inventory_authorized_keys = {
    ansible = compact([
      for key in split("\n", trimspace(try(local.proxmox_inventory_group_vars.ansible_authorized_keys, ""))) :
      trimspace(key)
    ])
    admin = compact([
      for key in split("\n", trimspace(try(local.proxmox_inventory_group_vars.muffin_authorized_keys, ""))) :
      trimspace(key)
    ])
  }

  proxmox_provider_ssh_nodes = {
    for fqdn, host in merge(
      try(local.proxmox_inventory_hosts.all.children.aah.hosts, {}),
      try(local.proxmox_inventory_hosts.all.children.lcy.hosts, {}),
    ) :
    fqdn => {
      address = host.ansible_host
      name    = split(".", fqdn)[0]
    } if try(host.ansible_host, null) != null
  }

  proxmox_vm_definition_files = sort(fileset(path.module, "proxmox_vms/**/*.vm.yml"))

  proxmox_vm_definition_docs = {
    for rel_path in local.proxmox_vm_definition_files :
    rel_path => yamldecode(file("${path.module}/${rel_path}"))
  }

  proxmox_vm_defaults = {
    agent = {
      enabled       = false
      timeout       = "3m"
      trim          = false
      wait_for_ipv4 = false
      wait_for_ipv6 = false
    }
    cpu = {
      cores   = 2
      sockets = 1
      type    = "x86-64-v2-AES"
    }
    memory = {
      dedicated = 2048
      floating  = 2048
      shared    = 0
    }
    network = {
      bridge   = "vmbr1"
      model    = "virtio"
      firewall = false
    }
    bios = "seabios"
    disk = {
      backup      = true
      discard     = "on"
      file_format = "raw"
      from_image  = false
      iothread    = true
      replicate   = true
      ssd         = true
    }
    vga = {
      memory = null
      type   = "serial0"
    }
    cloud_init = {
      admin_authorized_keys = []
      admin_user            = var.proxmox_vm_default_admin_user
      datastore_id          = null
      dns_search_domain     = ""
      dns_servers           = []
      interface             = "ide2"
      password              = null
      snippets_datastore_id = var.proxmox_vm_default_snippets_datastore_id
      ssh_authorized_keys   = []
      user                  = var.proxmox_vm_default_user
    }
    ha = {
      enabled      = false
      group        = null
      max_relocate = 1
      max_restart  = 1
      state        = "started"
    }
    replication = {
      comment  = null
      disable  = false
      enabled  = false
      rate     = null
      schedule = "*/15"
      target   = null
      type     = "local"
    }
    description      = "Managed by Terraform"
    on_boot          = true
    operating_system = "l26"
    scsi_hardware    = "virtio-scsi-single"
    started          = true
    tags             = ["ansible"]
  }

  proxmox_vms = {
    for rel_path, doc in local.proxmox_vm_definition_docs :
    coalesce(try(doc.name, null), trimsuffix(basename(rel_path), ".vm.yml")) => {
      source_file = rel_path
      name        = coalesce(try(doc.name, null), trimsuffix(basename(rel_path), ".vm.yml"))
      hostname    = doc.hostname
      description = coalesce(try(doc.description, null), local.proxmox_vm_defaults.description)
      node_name   = doc.node_name
      vm_id       = doc.vm_id
      on_boot     = coalesce(try(doc.on_boot, null), local.proxmox_vm_defaults.on_boot)
      operating_system = coalesce(
        try(doc.operating_system, null),
        local.proxmox_vm_defaults.operating_system,
      )
      scsi_hardware = coalesce(try(doc.scsi_hardware, null), local.proxmox_vm_defaults.scsi_hardware)
      started       = coalesce(try(doc.started, null), local.proxmox_vm_defaults.started)
      tags = sort(distinct(concat(
        local.proxmox_vm_defaults.tags,
        try(doc.tags, []),
        ["terraform", coalesce(try(doc.name, null), trimsuffix(basename(rel_path), ".vm.yml"))],
      )))
      cpu     = merge(local.proxmox_vm_defaults.cpu, try(doc.cpu, {}))
      memory  = merge(local.proxmox_vm_defaults.memory, try(doc.memory, {}))
      network = merge(local.proxmox_vm_defaults.network, try(doc.network, {}))
      disks = [
        for idx, disk in try(doc.disks, []) : merge(
          local.proxmox_vm_defaults.disk,
          disk,
          {
            from_image = coalesce(try(disk.from_image, null), idx == 0)
          }
        )
      ]
      image = merge(
        var.proxmox_vm_default_image,
        try(doc.image, {}),
        { node_name = coalesce(try(doc.image.node_name, null), doc.node_name) },
      )
      cloud_init = merge(
        local.proxmox_vm_defaults.cloud_init,
        try(doc.cloud_init, {}),
        {
          datastore_id = coalesce(
            try(doc.cloud_init.datastore_id, null),
            try(doc.disks[0].datastore_id, null),
          )
          dns_search_domain = trimspace(try(doc.cloud_init.dns_search_domain, "")) != "" ? trimspace(doc.cloud_init.dns_search_domain) : (
            trimspace(var.proxmox_vm_default_dns_search_domain) != "" ? trimspace(var.proxmox_vm_default_dns_search_domain) : (
              length(split(".", doc.hostname)) > 1 ? join(".", slice(split(".", doc.hostname), 1, length(split(".", doc.hostname)))) : ""
            )
          )
          dns_servers = length(try(doc.cloud_init.dns_servers, [])) > 0 ? doc.cloud_init.dns_servers : var.proxmox_vm_default_dns_servers
          snippets_datastore_id = try(doc.cloud_init.snippets_datastore_id, null) != null ? doc.cloud_init.snippets_datastore_id : var.proxmox_vm_default_snippets_datastore_id
          ssh_authorized_keys = distinct(compact(concat(
            local.proxmox_vm_inventory_authorized_keys.ansible,
            var.proxmox_vm_default_authorized_keys,
            try(doc.cloud_init.ssh_authorized_keys, []),
          )))
          admin_authorized_keys = distinct(compact(concat(
            local.proxmox_vm_inventory_authorized_keys.admin,
            try(doc.cloud_init.admin_authorized_keys, []),
          )))
        }
      )
      bios           = coalesce(try(doc.bios, null), local.proxmox_vm_defaults.bios)
      boot_interface = try(doc.boot_interface, null)
      efidisk        = try(doc.efidisk, null)
      tpm_state      = try(doc.tpm_state, null)
      vga            = merge(local.proxmox_vm_defaults.vga, try(doc.vga, {}))
      agent          = merge(local.proxmox_vm_defaults.agent, try(doc.agent, {}))
      startup        = try(doc.startup, null)
      ha             = merge(local.proxmox_vm_defaults.ha, try(doc.ha, {}))
      replication    = merge(
        local.proxmox_vm_defaults.replication,
        try(doc.replication, {}),
        {
          # Auto-derive target from cluster peers
          target = try(doc.replication.target, null) != null ? doc.replication.target : try(
            [for n in local.proxmox_cluster_nodes[split("/", rel_path)[1]] : n if n != doc.node_name][0],
            null
          )
        }
      )
      dns = {
        fqdn = doc.hostname
        ip   = split("/", doc.network.ipv4_address)[0]
        name = split(".", doc.hostname)[0]
        zone = length(split(".", doc.hostname)) > 1 ? join(".", slice(split(".", doc.hostname), 1, length(split(".", doc.hostname)))) : ""
      }
    }
  }

  # Maps cluster group name
  proxmox_cluster_nodes = {
    for cluster_name, cluster in try(local.proxmox_inventory_hosts.all.children.proxmox.children, {}) :
    cluster_name => [for fqdn in keys(try(cluster.hosts, {})) : split(".", fqdn)[0]]
  }

  proxmox_vm_download_groups = {
    for _, vm in local.proxmox_vms :
    "${vm.image.node_name}:${vm.image.datastore_id}:${vm.image.file_name}" => vm.image...
    if length([for disk in vm.disks : disk if disk.from_image]) > 0
  }

  proxmox_vm_downloads = {
    for key, images in local.proxmox_vm_download_groups :
    key => images[0]
  }

  proxmox_vm_boot_disk_interface = {
    for name, vm in local.proxmox_vms :
    name => coalesce(
      vm.boot_interface,
      one([for disk in vm.disks : disk.interface if disk.from_image])
    )
  }

  proxmox_vm_download_key = {
    for name, vm in local.proxmox_vms :
    name => "${vm.image.node_name}:${vm.image.datastore_id}:${vm.image.file_name}"
  }

  proxmox_vm_cloud_init_admin_users = {
    for name, vm in local.proxmox_vms :
    name => vm if(
      trimspace(vm.cloud_init.admin_user) != "" &&
      try(vm.cloud_init.snippets_datastore_id, null) != null
    )
  }

  proxmox_vm_cloud_init_user_data = {
    for name, vm in local.proxmox_vm_cloud_init_admin_users :
    name => join("\n", [
      "#cloud-config",
      yamlencode({
        disable_root = true
        ssh_pwauth   = false
        packages     = ["qemu-guest-agent"]
        runcmd       = ["systemctl enable --now qemu-guest-agent"]
        users = concat(
          length(vm.cloud_init.ssh_authorized_keys) > 0 ? [{
            name                = vm.cloud_init.user
            groups              = ["sudo"]
            lock_passwd         = true
            shell               = "/bin/bash"
            ssh_authorized_keys = vm.cloud_init.ssh_authorized_keys
            sudo                = "ALL=(ALL) NOPASSWD:ALL"
          }] : [],
          [{
            name                = vm.cloud_init.admin_user
            groups              = ["sudo"]
            lock_passwd         = true
            shell               = "/bin/bash"
            ssh_authorized_keys = vm.cloud_init.admin_authorized_keys
            sudo                = "ALL=(ALL) NOPASSWD:ALL"
          }]
        )
      }),
    ])
  }

  proxmox_vm_dns_records = {
    for _, vm in local.proxmox_vms :
    vm.dns.fqdn => {
      ip   = vm.dns.ip
      name = vm.dns.name
      zone = vm.dns.zone
    }
  }

  proxmox_vm_hostnames = [for vm in values(local.proxmox_vms) : vm.hostname]
  proxmox_vm_ipv4s     = [for vm in values(local.proxmox_vms) : vm.dns.ip]
  proxmox_vm_vmids     = [for vm in values(local.proxmox_vms) : tostring(vm.vm_id)]
  proxmox_lxc_fqdns    = [for record in var.lxc_dns_records : "${record.name}.${record.zone}"]
  proxmox_lxc_ipv4s    = [for record in var.lxc_dns_records : record.ip]
  proxmox_infra_fqdns  = keys(local.aah_infra_records)
  proxmox_infra_ipv4s  = [for record in values(local.aah_infra_records) : record.ip]
}

check "proxmox_vm_unique_vmids" {
  assert {
    condition     = length(local.proxmox_vm_vmids) == length(distinct(local.proxmox_vm_vmids))
    error_message = "Duplicate Proxmox VM IDs detected in tf/proxmox_vms/**/*.vm.yml."
  }
}

check "proxmox_vm_unique_hostnames" {
  assert {
    condition = (
      length(local.proxmox_vm_hostnames) == length(distinct(local.proxmox_vm_hostnames)) &&
      length(setintersection(toset(local.proxmox_vm_hostnames), toset(local.proxmox_lxc_fqdns))) == 0 &&
      length(setintersection(toset(local.proxmox_vm_hostnames), toset(local.proxmox_infra_fqdns))) == 0
    )
    error_message = "Proxmox VM hostnames must be unique across VM, LXC, and static infrastructure records."
  }
}

check "proxmox_vm_unique_ipv4s" {
  assert {
    condition = (
      length(local.proxmox_vm_ipv4s) == length(distinct(local.proxmox_vm_ipv4s)) &&
      length(setintersection(toset(local.proxmox_vm_ipv4s), toset(local.proxmox_lxc_ipv4s))) == 0 &&
      length(setintersection(toset(local.proxmox_vm_ipv4s), toset(local.proxmox_infra_ipv4s))) == 0
    )
    error_message = "Proxmox VM IPv4 addresses must be unique across VM, LXC, and static infrastructure records."
  }
}

check "proxmox_vm_required_shape" {
  assert {
    condition = alltrue([
      for vm in values(local.proxmox_vms) :
      length(vm.disks) > 0 &&
      (
        try(vm.boot_interface, null) != null ||
        length([for disk in vm.disks : disk if disk.from_image]) == 1
      ) &&
      length(vm.dns.zone) > 0 &&
      (
        length(vm.cloud_init.ssh_authorized_keys) > 0 ||
        try(vm.cloud_init.password, null) != null
      ) &&
      (
        trimspace(vm.cloud_init.admin_user) == "" ||
        try(vm.cloud_init.snippets_datastore_id, null) == null ||
        length(vm.cloud_init.admin_authorized_keys) > 0
      ) &&
      (
        !vm.replication.enabled ||
        try(vm.replication.target, null) != null
      ) &&
      (
        (!vm.agent.wait_for_ipv4 && !vm.agent.wait_for_ipv6) ||
        vm.agent.enabled
      )
    ])
    error_message = "Each Proxmox VM needs a FQDN hostname, at least one disk, either a boot_interface or exactly one image-backed boot disk, bootstrap login material, admin-user SSH keys when snippet-based admin bootstrap is enabled, and a replication target when replication is enabled."
  }
}

resource "proxmox_download_file" "debian_cloud_image" {
  for_each = local.proxmox_vm_downloads

  content_type = "import"
  datastore_id = each.value.datastore_id
  file_name    = each.value.file_name
  node_name    = each.value.node_name
  overwrite    = try(each.value.overwrite, false)
  url          = each.value.url
  verify       = try(each.value.verify, true)
}

resource "proxmox_virtual_environment_file" "cloud_init_user_data" {
  for_each = local.proxmox_vm_cloud_init_admin_users

  content_type = "snippets"
  datastore_id = each.value.cloud_init.snippets_datastore_id
  node_name    = each.value.node_name
  overwrite    = true

  source_raw {
    data      = local.proxmox_vm_cloud_init_user_data[each.key]
    file_name = "${each.value.name}.user-data.yaml"
  }
}

resource "proxmox_virtual_environment_vm" "vm" {
  for_each = local.proxmox_vms

  bios        = each.value.bios
  name        = each.value.name
  description = each.value.description
  node_name   = each.value.node_name
  vm_id       = each.value.vm_id
  on_boot     = each.value.on_boot
  operating_system {
    type = each.value.operating_system
  }
  scsi_hardware = each.value.scsi_hardware
  started       = each.value.started
  tags          = each.value.tags
  boot_order    = [local.proxmox_vm_boot_disk_interface[each.key]]

  agent {
    enabled = each.value.agent.enabled
    timeout = each.value.agent.timeout
    trim    = each.value.agent.trim

    dynamic "wait_for_ip" {
      for_each = each.value.agent.wait_for_ipv4 || each.value.agent.wait_for_ipv6 ? [1] : []
      content {
        ipv4 = each.value.agent.wait_for_ipv4
        ipv6 = each.value.agent.wait_for_ipv6
      }
    }
  }

  cpu {
    cores   = each.value.cpu.cores
    sockets = each.value.cpu.sockets
    type    = each.value.cpu.type
  }

  memory {
    dedicated = each.value.memory.dedicated
    floating  = each.value.memory.floating
    shared    = each.value.memory.shared
  }

  dynamic "disk" {
    for_each = each.value.disks
    content {
      backup       = disk.value.backup
      datastore_id = disk.value.datastore_id
      discard      = disk.value.discard
      file_format  = disk.value.file_format
      import_from  = disk.value.from_image ? proxmox_download_file.debian_cloud_image[local.proxmox_vm_download_key[each.key]].id : null
      interface    = disk.value.interface
      iothread     = disk.value.iothread
      replicate    = disk.value.replicate
      size         = disk.value.size_gb
      ssd          = disk.value.ssd
    }
  }

  initialization {
    datastore_id = each.value.cloud_init.datastore_id
    interface    = each.value.cloud_init.interface
    user_data_file_id = try(
      proxmox_virtual_environment_file.cloud_init_user_data[each.key].id,
      null,
    )

    dns {
      domain  = each.value.cloud_init.dns_search_domain
      servers = each.value.cloud_init.dns_servers
    }

    ip_config {
      ipv4 {
        address = each.value.network.ipv4_address
        gateway = each.value.network.ipv4_gateway
      }
    }

    user_account {
      keys     = each.value.cloud_init.ssh_authorized_keys
      password = each.value.cloud_init.password
      username = each.value.cloud_init.user
    }
  }

  network_device {
    bridge   = each.value.network.bridge
    firewall = each.value.network.firewall
    model    = each.value.network.model
    vlan_id  = try(each.value.network.vlan_id, null)
  }

  dynamic "startup" {
    for_each = each.value.startup == null ? [] : [each.value.startup]
    content {
      order      = tostring(try(startup.value.order, 0))
      up_delay   = tostring(try(startup.value.up_delay, 0))
      down_delay = tostring(try(startup.value.down_delay, 0))
    }
  }

  dynamic "efi_disk" {
    for_each = each.value.efidisk != null ? [each.value.efidisk] : []
    content {
      datastore_id      = efi_disk.value.datastore_id
      file_format       = try(efi_disk.value.file_format, "raw")
      pre_enrolled_keys = try(efi_disk.value.pre_enrolled_keys, false)
      type              = try(efi_disk.value.type, "4m")
    }
  }

  dynamic "tpm_state" {
    for_each = each.value.tpm_state != null ? [each.value.tpm_state] : []
    content {
      datastore_id = tpm_state.value.datastore_id
      version      = try(tpm_state.value.version, "v2.0")
    }
  }

  serial_device {}

  vga {
    memory = each.value.vga.memory
    type   = each.value.vga.type
  }

  lifecycle {
    ignore_changes = [
      initialization,
    ]
  }
}

resource "proxmox_haresource" "vm" {
  for_each = {
    for name, vm in local.proxmox_vms :
    name => vm if vm.ha.enabled
  }

  resource_id  = "vm:${each.value.vm_id}"
  comment      = "Managed by Terraform (${each.key})"
  group        = each.value.ha.group
  max_relocate = each.value.ha.max_relocate
  max_restart  = each.value.ha.max_restart
  state        = each.value.ha.state

  depends_on = [proxmox_virtual_environment_vm.vm]
}

resource "proxmox_replication" "vm" {
  for_each = {
    for name, vm in local.proxmox_vms :
    name => vm if vm.replication.enabled
  }

  comment  = coalesce(each.value.replication.comment, "Managed by Terraform (${each.key})")
  disable  = each.value.replication.disable
  id       = "${each.value.vm_id}-0"
  rate     = each.value.replication.rate
  schedule = each.value.replication.schedule
  target   = each.value.replication.target
  type     = each.value.replication.type

  depends_on = [proxmox_virtual_environment_vm.vm]
}

output "proxmox_vm_hosts" {
  description = "Terraform-managed Proxmox VM hostname and IPv4 mapping"
  value = {
    for name, vm in local.proxmox_vms :
    name => {
      hostname = vm.hostname
      ipv4     = vm.dns.ip
      node     = vm.node_name
    }
  }
}
