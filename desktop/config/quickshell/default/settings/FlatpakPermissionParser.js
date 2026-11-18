// Flatpak Context lists use ! to remove a permission from a lower layer.
function validId(id) { return /^[A-Za-z0-9._-]+$/.test(id) }
function parse(text, state) {
    state = state || {}
    var section = ''
    text.split(/\r?\n/).forEach(function(line) {
        line = line.trim()
        if (line[0] === '[' && line[line.length - 1] === ']') { section = line.slice(1, -1); return }
        var pos = line.indexOf('=')
        if (pos < 0 || !section) return
        if (section !== 'Context') {
            if (!state[section]) state[section] = {}
            var policyKey = line.slice(0, pos)
            state[section][policyKey] = line.slice(pos + 1) === 'none' ? false : policyKey + '=' + line.slice(pos + 1)
            return
        }
        var key = line.slice(0, pos), values = line.slice(pos + 1).split(';')
        if (!state[key]) state[key] = {}
        values.forEach(function(value) {
            if (!value) return
            var denied = value[0] === '!'
            if (denied) value = value.slice(1)
            var name = value.split(':')[0]
            state[key][name] = denied ? false : value
        })
    })
    return state
}
function has(state, group, name) { return !!(state[group] && state[group][name]) }
function command(action, id, enabled) {
    if (!validId(id)) throw new Error('Invalid application ID')
    var args = ['windoesnot-bounded', '15', 'flatpak']
    if (action === 'info') return args.concat(['info', '--show-permissions', id])
    if (action === 'show') return args.concat(['override', '--user', '--show', id])
    if (action === 'reset') return args.concat(['override', '--user', '--reset', id])
    if (action === 'portalReset') return args.concat(['permission-reset', id])
    var options = { network: 'share=network', home: 'filesystem=home', devices: 'device=all' }
    if (!options[action]) throw new Error('Invalid action')
    return args.concat(['override', '--user', '--' + (enabled ? '' : 'no') + options[action], id])
}
function apps(text) {
    return text.split(/\r?\n/).map(function(line) {
        var parts = line.split('\t'), id = (parts[0] || '').trim()
        return validId(id) ? { id: id, name: (parts[1] || id).trim() } : null
    }).filter(function(app) { return app !== null })
}
function portals(text, id) {
    return text.split(/\r?\n/).filter(function(line) {
        var parts = line.split('\t')
        return parts.length >= 4 && parts[2].trim() === id
    }).join('\n')
}
function details(state) {
    return Object.keys(state).map(function(group) {
        var values = Object.keys(state[group]).filter(function(key) { return state[group][key] }).map(function(key) { return state[group][key] })
        return values.length ? group + ': ' + values.join(', ') : ''
    }).filter(function(line) { return line }).join('\n')
}

// Structured rows of the saved portal decisions of one app (table, object, app, permissions, data).
function portalRows(text, id) {
    return text.split(/\r?\n/).map(function(line) {
        var parts = line.split('\t')
        if (parts.length < 4 || parts[2].trim() !== id) return null
        var data = (parts[4] || '').trim()
        var path = /b'([^']*)'/.exec(data)
        return { table: parts[0].trim(), object: parts[1].trim(), permissions: parts[3].trim().split(',').filter(function(p) { return p }),
                 path: path ? path[1] : '', data: path ? '' : data }
    }).filter(function(row) { return row !== null })
}
function baseName(path) { var i = path.lastIndexOf('/'); return i >= 0 ? path.slice(i + 1) : path }
function detailRows(state) {
    return Object.keys(state).map(function(group) {
        var values = Object.keys(state[group]).filter(function(key) { return state[group][key] }).map(function(key) { return state[group][key] })
        return values.length ? { group: group, values: values.join('\n') } : null
    }).filter(function(row) { return row !== null })
}
