<template>
  <div class="channels-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          :placeholder="$t('channels.searchPlaceholder')"
          :prefix-icon="Search"
          clearable
          class="toolbar-search"
          @input="handleSearch"
        />
        <el-select 
          v-model="statusFilter" 
          :placeholder="$t('channels.statusFilter')" 
          clearable
          class="toolbar-filter"
          @change="handleFilterChange"
        >
          <el-option :label="$t('common.all')" value="" />
          <el-option :label="$t('channels.online')" value="online" />
          <el-option :label="$t('channels.offline')" value="offline" />
        </el-select>
        <el-select 
          v-model="protocolFilter" 
          :placeholder="$t('channels.protocolFilter')" 
          clearable
          class="toolbar-filter"
          @change="handleFilterChange"
        >
          <el-option :label="$t('common.all')" value="" />
          <el-option label="MQTT" value="mqtt" />
          <el-option label="XNC" value="xnc" />
          <el-option label="HTTP" value="http" />
        </el-select>
        <div class="toolbar-stats">
          <span class="stat-item">
            <span class="stat-value">{{ channelStore.totalChannels }}</span>
            <span class="stat-label">{{ $t('channels.channels') }}</span>
          </span>
          <span class="stat-divider">/</span>
          <span class="stat-item stat-online">
            <span class="stat-value">{{ channelStore.onlineChannels }}</span>
            <span class="stat-label">{{ $t('channels.online') }}</span>
          </span>
        </div>
      </div>
      <div class="toolbar-right">
        <el-button v-if="userStore.hasPermission('devices', 'create')" type="primary" :icon="Plus" @click="handleAddChannel">
          {{ $t('channels.addChannel') }}
        </el-button>
        <el-button :icon="Download" @click="handleExportYaml">
          {{ $t('common.export') }}
        </el-button>
        <el-button v-if="userStore.hasPermission('devices', 'create')" :icon="Upload" @click="handleImportYaml">
          {{ $t('common.import') }}
        </el-button>
        <el-button :icon="Refresh" @click="handleRefresh" :loading="channelStore.loading">
          {{ $t('common.refresh') }}
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="channelStore.error"
      :title="channelStore.error"
      type="error"
      show-icon
      closable
      style="margin-bottom: 16px"
    />
    
    <div v-if="isCompactMode" class="main-content compact-mode">
      <div class="compact-tabs">
        <div 
          class="compact-tab" 
          :class="{ active: activeTab === 'channels' }"
          @click="activeTab = 'channels'"
        >
          {{ $t('channels.channelList') }}
          <span v-if="selectedChannelId" class="tab-badge">{{ selectedChannel?.name }}</span>
        </div>
        <div 
          class="compact-tab" 
          :class="{ active: activeTab === 'details', disabled: !selectedChannelId }"
          @click="selectedChannelId && (activeTab = 'details')"
        >
          {{ $t('channels.channelDetails') }}
        </div>
      </div>
      
      <div v-show="activeTab === 'channels'" class="compact-panel channel-panel">
        <div v-if="channelStore.loading && channelStore.channels.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>{{ $t('channels.loadingChannelList') }}</p>
        </div>

        <div v-else-if="filteredChannels.length === 0" class="empty-state">
          <p>{{ $t('channels.noChannels') }}</p>
        </div>

        <div v-else class="channel-grid">
          <div 
            v-for="channel in filteredChannels" 
            :key="channel.id" 
            class="channel-card-compact"
            :class="{ 
              offline: channel.connectionStatus !== 'online',
              selected: selectedChannelId === channel.id 
            }"
            @click="handleViewDetails(channel.id); activeTab = 'details'"
          >
            <div class="channel-card-header">
              <div class="channel-card-status" :class="{ online: channel.connectionStatus === 'online' }">
                <el-icon v-if="channel.connectionStatus === 'online'"><CircleCheck /></el-icon>
                <el-icon v-else><CircleClose /></el-icon>
              </div>
              <div class="channel-card-info">
                <div class="channel-card-name">{{ channel.name }}</div>
                <div class="channel-card-meta">
                  <span>{{ channel.protocol.toUpperCase() }}</span>
                  <span>{{ channel.uploadRate }} {{ $t('channels.itemsPerMin') }}</span>
                </div>
              </div>
            </div>
            <div class="channel-card-stats">
              <div class="stat-mini">
                <span class="stat-mini-label">{{ $t('channels.successRate') }}</span>
                <span class="stat-mini-value">{{ channel.successRate }}%</span>
              </div>
              <div class="stat-mini">
                <span class="stat-mini-label">{{ $t('channels.backlog') }}</span>
                <span class="stat-mini-value">{{ channel.backlogCount }}</span>
              </div>
            </div>
            <div class="channel-card-actions">
              <el-switch
                v-if="userStore.hasPermission('devices', 'update')"
                :model-value="channel.enabled" 
                :size="isTouch ? 'default' : 'small'"
                @change="handleToggleChannel(channel.id)"
                @click.stop
              />
              <div class="action-buttons" @click.stop>
                <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" link :size="isTouch ? 'default' : 'small'" @click="handleEditChannel(channel)">
                  {{ $t('common.edit') }}
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'delete')" type="danger" link :size="isTouch ? 'default' : 'small'" @click="handleDeleteChannel(channel)">
                  {{ $t('common.delete') }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div v-show="activeTab === 'details'" class="compact-panel details-panel">
        <div v-if="!selectedChannelId" class="empty-details">
          <el-icon :size="48"><Connection /></el-icon>
          <p>{{ $t('channels.selectChannelFirst') }}</p>
          <el-button type="primary" @click="activeTab = 'channels'">{{ $t('channels.backToChannelList') }}</el-button>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <div class="panel-header-left">
              <el-button link @click="activeTab = 'channels'">
                <el-icon><RefreshRight /></el-icon>
                {{ $t('channels.backToChannels') }}
              </el-button>
            </div>
            <span class="panel-title">{{ selectedChannel?.name }}</span>
            <div class="header-info">
              <span class="status-dot" :class="{ online: selectedChannel?.status === 'online' }"></span>
              <span class="protocol-tag">{{ selectedChannel?.protocol?.toUpperCase() }}</span>
            </div>
            <div class="header-actions">
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" size="small" plain @click="handleTestConnection(selectedChannelId!)">
                {{ $t('common.test') }}
              </el-button>
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="warning" size="small" plain @click="handleRestartChannel(selectedChannelId!)">
                {{ $t('channels.restart') }}
              </el-button>
            </div>
          </div>

          <div v-if="selectedChannel" class="channel-details-content">
            <!-- 统计仪表盘 -->
            <div v-if="selectedChannel.statistics" class="stats-dashboard">
              <div class="stat-item">
                <div class="stat-icon upload-icon">↑</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.upload_rate }}</div>
                  <div class="stat-label">{{ $t('channels.itemsPerMin') }}</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon success-icon">✓</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.success_rate }}%</div>
                  <div class="stat-label">{{ $t('channels.successRate') }}</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon backlog-icon">⏳</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.backlog_count }}</div>
                  <div class="stat-label">{{ $t('channels.backlog') }}</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon total-icon">📊</div>
                <div class="stat-content">
                  <div class="stat-value">{{ formatNumber(selectedChannel.statistics.total_uploaded) }}</div>
                  <div class="stat-label">{{ $t('channels.totalUploaded') }}</div>
                </div>
              </div>
            </div>

            <!-- 连接配置（合并基本信息） -->
            <div class="config-section">
              <div class="section-title">{{ $t('channels.connectionConfig') }}</div>
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-label">{{ $t('channels.channelId') }}</span>
                  <span class="config-value">{{ selectedChannel.id }}</span>
                </div>
                <div class="config-item">
                  <span class="config-label">{{ $t('channels.name') }}</span>
                  <span class="config-value">{{ selectedChannel.name }}</span>
                </div>
                <template v-if="selectedChannel.protocol === 'mqtt'">
                  <div class="config-item">
                    <span class="config-label">Broker</span>
                    <span class="config-value">{{ selectedChannel.connection.broker }}:{{ selectedChannel.connection.port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.clientId') }}</span>
                    <span class="config-value code">{{ selectedChannel.connection.client_id }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.topic') }}</span>
                    <span class="config-value code">{{ selectedChannel.connection.topic }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">QoS</span>
                    <span class="config-value">{{ selectedChannel.connection.qos }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.keepalive') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.keepalive }}{{ $t('channels.seconds') }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.adapter') }}</span>
                    <span class="config-value">
                      <el-tag v-if="selectedChannel.adapter.adapter" size="small" type="primary">{{ selectedChannel.adapter.adapter }}</el-tag>
                      <span v-else class="muted">{{ $t('channels.standard') }}</span>
                    </span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'xnc'">
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.localPort') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.local_port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.remoteHost') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_host || '--' }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.remotePort') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_port || '--' }}</span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'http'">
                  <div class="config-item full-width">
                    <span class="config-label">{{ $t('channels.endpoint') }}</span>
                    <span class="config-value code">{{ selectedChannel.connection.endpoint }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.method') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.method }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.timeout') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.timeout }}{{ $t('channels.seconds') }}</span>
                  </div>
                </template>
              </div>
              <!-- 适配器配置JSON -->
              <div v-if="selectedChannel.protocol === 'mqtt' && selectedChannel.adapter.config && Object.keys(selectedChannel.adapter.config).length > 0" class="adapter-config">
                <div class="adapter-config-title">{{ $t('channels.adapterConfig') }}</div>
                <pre class="json-config">{{ JSON.stringify(selectedChannel.adapter.config, null, 2) }}</pre>
              </div>
            </div>

            <!-- 上传策略（可折叠） -->
            <el-collapse class="detail-collapse">
              <el-collapse-item :title="$t('channels.uploadStrategy')">
                <div class="config-grid">
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.immediateUpload') }}</span>
                    <span class="config-value">
                      <el-tag :type="selectedChannel.upload_strategy.immediate_upload ? 'success' : 'info'" size="small">
                        {{ selectedChannel.upload_strategy.immediate_upload ? $t('common.yes') : $t('common.no') }}
                      </el-tag>
                    </span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.batchSize') }}</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.batch_size }} {{ $t('channels.items') }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.uploadInterval') }}</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.interval }} {{ $t('channels.seconds') }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.retryTimes') }}</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.retry_times }} {{ $t('channels.times') }}</span>
                  </div>
                </div>
              </el-collapse-item>
              <el-collapse-item v-if="selectedChannel.description" :title="$t('channels.description')">
                <p class="description-text">{{ selectedChannel.description }}</p>
              </el-collapse-item>
            </el-collapse>
          </div>
        </template>
      </div>
    </div>
    
    <div v-else class="main-content">
      <div class="channel-list-panel">
        <div class="panel-header">
          <span class="panel-title">{{ $t('channels.channelList') }}</span>
          <span class="channel-count">{{ filteredChannels.length }} {{ $t('channels.channelsCount') }}</span>
        </div>
        
        <div v-if="channelStore.loading && channelStore.channels.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>{{ $t('channels.loadingChannelList') }}</p>
        </div>

        <div v-else-if="filteredChannels.length === 0" class="empty-state">
          <p>{{ $t('channels.noChannels') }}</p>
        </div>

        <div v-else class="channel-list">
          <div 
            v-for="channel in filteredChannels" 
            :key="channel.id" 
            class="channel-item"
            :class="{ 
              offline: channel.connectionStatus !== 'online',
              selected: selectedChannelId === channel.id 
            }"
            @click="handleViewDetails(channel.id)"
          >
            <div class="channel-item-status" :class="{ online: channel.connectionStatus === 'online' }">
              <el-icon v-if="channel.connectionStatus === 'online'"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
            </div>
            <div class="channel-item-content">
              <div class="channel-item-header">
                <span class="channel-item-name">{{ channel.name }}</span>
              </div>
              <div class="channel-item-meta">
                <span>{{ channel.protocol.toUpperCase() }}</span>
                <span>{{ channel.uploadRate }} {{ $t('channels.itemsPerMin') }}</span>
                <span>{{ channel.successRate }}%</span>
              </div>
            </div>
            <div class="channel-item-actions" @click.stop>
              <el-switch
                v-if="userStore.hasPermission('devices', 'update')"
                :model-value="channel.enabled" 
                :size="isTouch ? 'default' : 'small'"
                @change="handleToggleChannel(channel.id)"
              />
              <el-dropdown trigger="click" @command="(cmd: string) => {
                if (cmd === 'edit') handleEditChannel(channel)
                else if (cmd === 'test') handleTestConnection(channel.id)
                else if (cmd === 'restart') handleRestartChannel(channel.id)
                else if (cmd === 'delete') handleDeleteChannel(channel)
              }">
                <el-button type="info" link :size="isTouch ? 'default' : 'small'" class="more-btn">
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'update')" command="edit" :icon="Edit">{{ $t('common.edit') }}</el-dropdown-item>
                    <el-dropdown-item command="test" :icon="Connection">{{ $t('channels.testConnection') }}</el-dropdown-item>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'update')" command="restart" :icon="RefreshRight">{{ $t('channels.restart') }}</el-dropdown-item>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'delete')" command="delete" :icon="Delete" divided>
                      <span class="danger-text">{{ $t('common.delete') }}</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </div>
      
      <div class="details-panel">
        <div v-if="!selectedChannelId" class="empty-details">
          <el-icon :size="48"><Connection /></el-icon>
          <p>{{ $t('channels.selectChannelFromLeft') }}</p>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <span class="panel-title">{{ selectedChannel?.name }}</span>
            <div class="header-info">
              <span class="status-dot" :class="{ online: selectedChannel?.status === 'online' }"></span>
              <span class="protocol-tag">{{ selectedChannel?.protocol?.toUpperCase() }}</span>
              <el-tag :type="selectedChannel?.enabled ? 'success' : 'info'" size="small">
                {{ selectedChannel?.enabled ? $t('channels.enabled') : $t('channels.disabled') }}
              </el-tag>
            </div>
            <div class="header-actions">
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" size="small" plain @click="handleTestConnection(selectedChannelId!)">
                {{ $t('channels.testConnection') }}
              </el-button>
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="warning" size="small" plain @click="handleRestartChannel(selectedChannelId!)">
                {{ $t('channels.restart') }}
              </el-button>
            </div>
          </div>

          <div v-if="selectedChannel" class="channel-details-content">

            <!-- 统计仪表盘 -->
            <div v-if="selectedChannel.statistics" class="stats-dashboard">
              <div class="stat-item">
                <div class="stat-icon upload-icon">↑</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.upload_rate }}</div>
                  <div class="stat-label">{{ $t('channels.itemsPerMin') }}</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon success-icon">✓</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.success_rate }}%</div>
                  <div class="stat-label">{{ $t('channels.successRate') }}</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon backlog-icon">⏳</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.backlog_count }}</div>
                  <div class="stat-label">{{ $t('channels.backlog') }}</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon total-icon">📊</div>
                <div class="stat-content">
                  <div class="stat-value">{{ formatNumber(selectedChannel.statistics.total_uploaded) }}</div>
                  <div class="stat-label">{{ $t('channels.totalUploaded') }}</div>
                </div>
              </div>
            </div>

            <!-- 连接配置（合并基本信息） -->
            <div class="config-section">
              <div class="section-title">{{ $t('channels.connectionConfig') }}</div>
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-label">{{ $t('channels.channelId') }}</span>
                  <span class="config-value">{{ selectedChannel.id }}</span>
                </div>
                <div class="config-item">
                  <span class="config-label">{{ $t('channels.name') }}</span>
                  <span class="config-value">{{ selectedChannel.name }}</span>
                </div>
                <template v-if="selectedChannel.protocol === 'mqtt'">
                  <div class="config-item">
                    <span class="config-label">Broker</span>
                    <span class="config-value">{{ selectedChannel.connection.broker }}:{{ selectedChannel.connection.port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.clientId') }}</span>
                    <span class="config-value code">{{ selectedChannel.connection.client_id }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.topic') }}</span>
                    <span class="config-value code">{{ selectedChannel.connection.topic }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">QoS</span>
                    <span class="config-value">{{ selectedChannel.connection.qos }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.keepalive') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.keepalive }}{{ $t('channels.seconds') }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.adapter') }}</span>
                    <span class="config-value">
                      <el-tag v-if="selectedChannel.adapter.adapter" size="small" type="primary">{{ selectedChannel.adapter.adapter }}</el-tag>
                      <span v-else class="muted">{{ $t('channels.standard') }}</span>
                    </span>
                  </div>
                  <div v-if="selectedChannel.connection.username" class="config-item">
                    <span class="config-label">{{ $t('channels.username') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.username }}</span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'xnc'">
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.localPort') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.local_port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.remoteHost') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_host || '--' }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.remotePort') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_port || '--' }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.reconnectInterval') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.reconnect_interval || 5 }}{{ $t('channels.seconds') }}</span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'http'">
                  <div class="config-item full-width">
                    <span class="config-label">{{ $t('channels.endpoint') }}</span>
                    <span class="config-value code">{{ selectedChannel.connection.endpoint }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.method') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.method }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.timeout') }}</span>
                    <span class="config-value">{{ selectedChannel.connection.timeout }}{{ $t('channels.seconds') }}</span>
                  </div>
                </template>
              </div>
              <!-- 适配器配置JSON -->
              <div v-if="selectedChannel.protocol === 'mqtt' && selectedChannel.adapter.config && Object.keys(selectedChannel.adapter.config).length > 0" class="adapter-config">
                <div class="adapter-config-title">{{ $t('channels.adapterConfig') }}</div>
                <pre class="json-config">{{ JSON.stringify(selectedChannel.adapter.config, null, 2) }}</pre>
              </div>
            </div>

            <!-- 上传策略（可折叠） -->
            <el-collapse class="detail-collapse">
              <el-collapse-item :title="$t('channels.uploadStrategy')">
                <div class="config-grid">
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.immediateUpload') }}</span>
                    <span class="config-value">
                      <el-tag :type="selectedChannel.upload_strategy.immediate_upload ? 'success' : 'info'" size="small">
                        {{ selectedChannel.upload_strategy.immediate_upload ? $t('common.yes') : $t('common.no') }}
                      </el-tag>
                    </span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.batchSize') }}</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.batch_size }} {{ $t('channels.items') }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.uploadInterval') }}</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.interval }} {{ $t('channels.seconds') }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">{{ $t('channels.retryTimes') }}</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.retry_times }} {{ $t('channels.times') }}</span>
                  </div>
                </div>
              </el-collapse-item>
              <el-collapse-item v-if="selectedChannel.description" :title="$t('channels.description')">
                <p class="description-text">{{ selectedChannel.description }}</p>
              </el-collapse-item>
            </el-collapse>
          </div>
        </template>
      </div>
    </div>
    
    <el-dialog
      v-model="showChannelDialog"
      :title="isEditing ? $t('channels.editChannel') : $t('channels.addChannel')"
      width="min(900px, 90vw)"
      :close-on-click-modal="false"
    >
      <el-form ref="channelFormRef" :model="channelForm" :rules="channelFormRules" label-width="100px">

        <!-- 卡片1: 基本信息 -->
        <el-card class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ $t('channels.basicInfo') }}</span>
              <el-tag type="danger" size="small">{{ $t('channels.required') }}</el-tag>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('channels.channelId')" prop="id">
                <el-input
                  v-model="channelForm.id"
                  :placeholder="$t('channels.channelIdHint')"
                  :disabled="isEditing"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('channels.channelName')" prop="name">
                <el-input v-model="channelForm.name" :placeholder="$t('channels.channelNameHint')" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('channels.protocolType')" prop="protocol">
                <el-select v-model="channelForm.protocol" :placeholder="$t('channels.selectProtocol')" @change="handleProtocolChange">
                  <el-option
                    v-for="opt in protocolOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('channels.enable')">
                <el-switch v-model="channelForm.enabled" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item :label="$t('channels.description')">
            <el-input v-model="channelForm.description" type="textarea" :rows="2" :placeholder="$t('channels.descriptionHint')" />
          </el-form-item>
        </el-card>

        <!-- 卡片2: 连接配置 -->
        <el-card class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ $t('channels.connectionConfig') }}</span>
              <el-tag type="danger" size="small">{{ $t('channels.required') }}</el-tag>
            </div>
          </template>

          <!-- MQTT/HTTP 连接配置 -->
          <template v-if="channelForm.protocol !== 'xnc'">
            <el-row :gutter="20">
              <el-col :span="16">
                <el-form-item :label="$t('channels.hostAddress')" prop="host">
                  <el-input v-model="channelForm.host" :placeholder="$t('channels.hostAddressHint')" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="$t('channels.port')">
                  <el-input-number v-model="channelForm.port" :min="1" :max="65535" class="full-width" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item :label="$t('channels.username')">
                  <el-input v-model="channelForm.username" :placeholder="$t('common.optional')" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="$t('channels.password')">
                  <el-input v-model="channelForm.password" type="password" :placeholder="$t('common.optional')" show-password />
                </el-form-item>
              </el-col>
            </el-row>
          </template>

          <!-- XNC 连接配置 -->
          <template v-if="channelForm.protocol === 'xnc'">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item :label="$t('channels.localPort')">
                  <el-input-number v-model="channelForm.local_port" :min="1024" :max="65535" class="full-width" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="$t('channels.remoteHost')">
                  <el-input v-model="channelForm.remote_host" :placeholder="$t('channels.remoteHostHint')" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="$t('channels.remotePort')">
                  <el-input-number v-model="channelForm.remote_port" :min="1" :max="65535" class="full-width" />
                </el-form-item>
              </el-col>
            </el-row>
          </template>
        </el-card>

        <!-- 卡片3: MQTT适配器配置 -->
        <el-card v-if="channelForm.protocol === 'mqtt'" class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ $t('channels.adapterConfig') }}</span>
              <el-tag v-if="channelForm.adapter === 'C001'" type="danger" size="small">{{ $t('channels.required') }}</el-tag>
              <el-tag v-else type="info" size="small">{{ $t('common.optional') }}</el-tag>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('channels.adapter')">
                <el-select v-model="channelForm.adapter" :placeholder="$t('channels.adapterHint')" filterable allow-create @change="handleAdapterChange">
                  <el-option
                    v-for="opt in mqttAdapterOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  >
                    <span>{{ opt.label }}</span>
                    <span class="option-desc">{{ opt.description }}</span>
                  </el-option>
                </el-select>
                <div class="form-hint">
                  {{ $t('channels.adapterHintText') }}
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12" v-if="channelForm.adapter === 'C001'">
              <el-form-item :label="$t('channels.productKey')" required>
                <el-input
                  v-model="productKey"
                  :placeholder="$t('channels.productKeyHint')"
                />
                <div class="form-hint">
                  {{ $t('channels.productKeyDesc') }}
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 客户A模板配置 -->
          <el-form-item v-if="channelForm.adapter === 'C001'" label=" ">
            <el-collapse class="full-width">
              <el-collapse-item :title="$t('channels.templateConfig')">
                <el-alert type="info" :closable="false" class="alert-with-margin">
                  {{ $t('channels.templateConfigHint') }}
                </el-alert>
                <el-input
                  v-model="channelForm.adapter_config"
                  type="textarea"
                  :rows="15"
                  :placeholder="$t('channels.jsonConfigHint')"
                />
              </el-collapse-item>
            </el-collapse>
          </el-form-item>

          <!-- 其他适配器JSON配置 -->
          <el-form-item v-else-if="channelForm.adapter !== 'standard'" :label="$t('channels.adapterConfig')">
            <el-input
              v-model="channelForm.adapter_config"
              type="textarea"
              :rows="5"
              :placeholder="$t('channels.adapterConfigHint')"
            />
            <div class="form-hint">
              {{ $t('channels.adapterConfigHintText') }}
            </div>
          </el-form-item>
        </el-card>

        <!-- 卡片4: 高级配置（默认折叠） -->
        <el-card class="config-card optional" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ $t('channels.advancedConfig') }}</span>
              <el-tag type="info" size="small">{{ $t('common.optional') }}</el-tag>
            </div>
          </template>
          <el-collapse>
            <!-- MQTT高级参数 -->
            <el-collapse-item v-if="channelForm.protocol === 'mqtt'" :title="$t('channels.mqttParams')">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('channels.clientId')">
                    <el-input v-model="channelForm.client_id" :placeholder="$t('channels.clientIdHint')" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="QoS">
                    <el-radio-group v-model="channelForm.qos">
                      <el-radio :value="0">{{ $t('channels.qos0') }}</el-radio>
                      <el-radio :value="1">{{ $t('channels.qos1') }}</el-radio>
                      <el-radio :value="2">{{ $t('channels.qos2') }}</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('channels.keepaliveTime')">
                    <el-input-number v-model="channelForm.keepalive" :min="10" :max="3600" />
                    <span class="unit-hint">{{ $t('channels.seconds') }}</span>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('channels.cleanSession')">
                    <el-switch v-model="channelForm.clean_session" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('channels.publishMode')">
                    <el-radio-group v-model="channelForm.publish_mode">
                      <el-radio value="single">{{ $t('channels.singleSend') }}</el-radio>
                      <el-radio value="batch">{{ $t('channels.batchSend') }}</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('channels.commandTimeout')">
                    <el-input-number v-model="channelForm.command_timeout" :min="5" :max="300" />
                    <span class="unit-hint">{{ $t('channels.seconds') }}</span>
                  </el-form-item>
                </el-col>
              </el-row>
              <!-- 客户A适配器不需要设置主题和命令主题 -->
              <template v-if="channelForm.adapter !== 'C001'">
                <el-row :gutter="20">
                  <el-col :span="12">
                    <el-form-item :label="$t('channels.topic')">
                      <el-input v-model="channelForm.topic" :placeholder="$t('channels.topicHint')" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item :label="$t('channels.commandTopic')">
                      <el-input v-model="channelForm.command_topic" :placeholder="$t('channels.commandTopicHint')" />
                    </el-form-item>
                  </el-col>
                </el-row>
              </template>
            </el-collapse-item>

            <!-- XNC高级参数 -->
            <el-collapse-item v-if="channelForm.protocol === 'xnc'" :title="$t('channels.xncParams')">
              <el-form-item :label="$t('channels.reconnectInterval')">
                <el-input-number v-model="channelForm.reconnect_interval" :min="1" :max="300" />
                <span class="unit-hint">{{ $t('channels.reconnectIntervalHint') }}</span>
              </el-form-item>
              <el-form-item :label="$t('channels.mappingConfig')">
                <el-input
                  v-model="channelForm.mapping_config"
                  type="textarea"
                  :rows="6"
                  :placeholder="$t('channels.mappingConfigHint')"
                />
                <div class="mapping-help">
                  <div class="mapping-help-text">
                    {{ $t('channels.mappingConfigHintText') }}
                  </div>
                  <el-button type="primary" link size="small" @click="fillMappingTemplate">
                    {{ $t('channels.fillTemplate') }}
                  </el-button>
                </div>
              </el-form-item>
            </el-collapse-item>

            <!-- HTTP高级参数 -->
            <el-collapse-item v-if="channelForm.protocol === 'http'" :title="$t('channels.httpParams')">
              <el-form-item :label="$t('channels.endpointUrl')">
                <el-input v-model="channelForm.endpoint" :placeholder="$t('channels.endpointUrlHint')" />
              </el-form-item>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('channels.requestMethod')">
                    <el-radio-group v-model="channelForm.method">
                      <el-radio value="GET">GET</el-radio>
                      <el-radio value="POST">POST</el-radio>
                      <el-radio value="PUT">PUT</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('channels.timeoutTime')">
                    <el-input-number v-model="channelForm.timeout" :min="1" :max="300" />
                    <span class="unit-hint">{{ $t('channels.seconds') }}</span>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item :label="$t('channels.requestHeaders')">
                <el-input
                  v-model="channelForm.headers"
                  type="textarea"
                  :rows="3"
                  :placeholder="$t('channels.requestHeadersHint')"
                />
              </el-form-item>
            </el-collapse-item>

            <!-- 上传策略 -->
            <el-collapse-item :title="$t('channels.uploadStrategy')">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('channels.immediateUpload')">
                    <el-switch v-model="channelForm.immediate_upload" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('channels.batchSize')">
                    <el-input-number v-model="channelForm.batch_size" :min="1" :max="10000" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item :label="$t('channels.uploadInterval')">
                    <el-input-number v-model="channelForm.interval" :min="1" :max="3600" />
                    <span class="unit-hint">{{ $t('channels.seconds') }}</span>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('channels.retryTimes')">
                    <el-input-number v-model="channelForm.retry_times" :min="0" :max="10" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item :label="$t('channels.retryInterval')">
                <el-input-number v-model="channelForm.retry_interval" :min="1" :max="300" />
                <span class="unit-hint">{{ $t('channels.retryIntervalHint') }}</span>
              </el-form-item>
            </el-collapse-item>

            <!-- 其他配置 -->
            <el-collapse-item :title="$t('channels.otherConfig')">
              <el-form-item :label="$t('channels.tags')">
                <el-input v-model="channelForm.tags" :placeholder="$t('channels.tagsHint')" />
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </el-card>

      </el-form>
      <template #footer>
        <el-button @click="showChannelDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveChannel" :loading="saving">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <input
      ref="importFileRef"
      type="file"
      accept=".yaml,.yml"
      style="display: none"
      @change="handleImportFileChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChannelStore } from '@/stores/channels'
import { useUserStore } from '@/stores/users'
import { channelApi } from '@/api/channels'
import type { NorthChannelConfig, NorthChannelProtocol } from '@/api/types'
import type { ChannelListItem } from '@/stores/channels'
import { useResponsive } from '@/utils/useResponsive'
import yaml from 'js-yaml'
import { 
  Plus, 
  Upload, 
  Download, 
  Refresh,
  CircleCheck,
  CircleClose,
  Search,
  Connection,
  Delete,
  Edit,
  MoreFilled,
  RefreshRight
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()

// XNC映射配置模板
const XNC_MAPPING_TEMPLATE = {
  "vdid_mapping": {
    "device_1": 1,
    "device_2": 2
  },
  "oid_mapping": {
    "device_1.temperature": 1,
    "device_1.humidity": 2,
    "device_2.pressure": 3
  },
  "pid": {
    "point_value": 85,
    "point_error": 103
  }
}

const channelStore = useChannelStore()
const userStore = useUserStore()
const { isTouch, isTablet, isMobile, width } = useResponsive()

const searchQuery = ref('')
const statusFilter = ref('')
const protocolFilter = ref('')
const selectedChannelId = ref<string | null>(null)

const activeTab = ref('channels')

const isCompactMode = computed(() => isTablet.value || isMobile.value || width.value <= 1024)

const filteredChannels = computed(() => {
  let list = channelStore.channelList
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    list = list.filter(c =>
      c.name.toLowerCase().includes(query) ||
      c.id.toLowerCase().includes(query) ||
      c.protocol.toLowerCase().includes(query)
    )
  }
  if (statusFilter.value === 'online') {
    list = list.filter(c => c.connectionStatus === 'online')
  } else if (statusFilter.value === 'offline') {
    list = list.filter(c => c.connectionStatus !== 'online')
  }
  if (protocolFilter.value) {
    list = list.filter(c => c.protocol === protocolFilter.value)
  }
  return list
})

const handleSearch = () => {}

const handleFilterChange = () => {}

const handleToggleChannel = async (id: string) => {
  try {
    await channelStore.toggleChannel(id)
    ElMessage.success(t('channels.statusChanged'))
  } catch (e: unknown) {
    ElMessage.error(t('channels.operationFailed', { message: e instanceof Error ? e.message : t('common.unknownError') }))
  }
}

const handleRefresh = async () => {
  await channelStore.fetchChannels()
}

const showChannelDialog = ref(false)
const channelForm = ref({
  id: '',
  name: '',
  description: '',
  enabled: true,
  protocol: 'mqtt' as NorthChannelProtocol,
  host: '',
  port: 1883,
  username: '',
  password: '',
  client_id: '',
  topic: '',
  qos: 0 as 0 | 1 | 2,
  keepalive: 60,
  clean_session: true,
  adapter: 'standard',
  adapter_config: '{}',
  command_topic: '',
  publish_mode: 'single' as 'single' | 'batch',
  command_timeout: 30,
  local_port: 8888,
  remote_host: '127.0.0.1',
  remote_port: 9000,
  reconnect_interval: 5,
  mapping_config: '{}',
  endpoint: '',
  method: 'POST' as 'GET' | 'POST' | 'PUT',
  headers: '{}',
  timeout: 30,
  immediate_upload: true,
  batch_size: 100,
  interval: 5,
  retry_times: 3,
  retry_interval: 5,
  tags: ''
})
const channelFormRef = ref()
const isEditing = ref(false)
const editingId = ref('')
const saving = ref(false)

const protocolOptions = [
  { 
    label: 'MQTT', 
    value: 'mqtt', 
    defaultPort: 1883,
    defaultConfig: {
      client_id: `xagent_${Date.now()}`,
      topic: 'data/upload',
      qos: 1,
      keepalive: 60,
      clean_session: true,
      command_topic: 'xagent/command',
      publish_mode: 'single',
      command_timeout: 30
    }
  },
  { 
    label: 'XNC', 
    value: 'xnc', 
    defaultPort: 9000,
    defaultConfig: { 
      local_port: 8888,
      remote_host: '127.0.0.1',
      remote_port: 9000,
      reconnect_interval: 5
    }
  },
  { 
    label: 'HTTP', 
    value: 'http', 
    defaultPort: 80,
    defaultConfig: { 
      method: 'POST',
      timeout: 30
    }
  }
]

const mqttAdapterOptions = [
  { label: t('channels.adapterStandard'), value: 'standard', description: t('channels.adapterStandardDesc') },
  { label: t('channels.adapterC001'), value: 'C001', description: t('channels.adapterC001Desc') },
]

// 适配器默认配置缓存（从后端API获取）
const adapterDefaultsCache = ref<Record<string, any>>({})

// 产品Key（独立存储，便于表单绑定）
const productKey = ref('')

// 获取适配器默认配置
const loadAdapterDefaults = async (adapterCode: string): Promise<any> => {
  if (adapterDefaultsCache.value[adapterCode]) {
    return adapterDefaultsCache.value[adapterCode]
  }

  try {
    const result = await channelApi.getAdapterDefaults(adapterCode)
    adapterDefaultsCache.value[adapterCode] = result.defaults
    return result.defaults
  } catch (e) {
    console.error('Failed to load adapter defaults:', e)
    return null
  }
}

// 同步 productKey 到 adapter_config
watch(productKey, (newVal) => {
  if (channelForm.value.adapter === 'C001') {
    try {
      const config = JSON.parse(channelForm.value.adapter_config || '{}')
      config.productKey = newVal
      channelForm.value.adapter_config = JSON.stringify(config, null, 2)
    } catch {
      // ignore
    }
  }
})

// 适配器变更处理
const handleAdapterChange = async (adapter: string) => {
  if (adapter === 'standard') {
    channelForm.value.adapter_config = '{}'
    productKey.value = ''
  } else {
    if (!isEditing.value || !channelForm.value.adapter_config || channelForm.value.adapter_config === '{}') {
      const defaults = await loadAdapterDefaults(adapter)
      if (defaults) {
        channelForm.value.adapter_config = JSON.stringify(defaults, null, 2)
        productKey.value = defaults.productKey || ''
      }
    }
  }
}

// 填充XNC映射配置模板
const fillMappingTemplate = () => {
  channelForm.value.mapping_config = JSON.stringify(XNC_MAPPING_TEMPLATE, null, 2)
}

const channelFormRules = {
  id: [{ required: true, message: t('channels.idRequired'), trigger: 'blur' }],
  name: [{ required: true, message: t('channels.nameRequired'), trigger: 'blur' }],
  protocol: [{ required: true, message: t('channels.protocolRequired'), trigger: 'change' }]
}

const handleProtocolChange = (val: NorthChannelProtocol) => {
  const opt = protocolOptions.find(o => o.value === val)
  if (opt) {
    channelForm.value.port = opt.defaultPort
    if (opt.defaultConfig) {
      Object.assign(channelForm.value, opt.defaultConfig)
    }
  }
}

const handleAddChannel = () => {
  isEditing.value = false
  editingId.value = ''
  productKey.value = ''
  channelForm.value = {
    id: '',
    name: '',
    description: '',
    enabled: true,
    protocol: 'mqtt',
    host: '',
    port: 1883,
    username: '',
    password: '',
    client_id: `xagent_${Date.now()}`,
    topic: 'data/upload',
    qos: 1,
    keepalive: 60,
    clean_session: true,
    adapter: 'standard',
    adapter_config: '{}',
    command_topic: '',
    publish_mode: 'single',
    command_timeout: 30,
    local_port: 8888,
    remote_host: '127.0.0.1',
    remote_port: 9000,
    reconnect_interval: 5,
    mapping_config: '{}',
    endpoint: '',
    method: 'POST',
    headers: '{}',
    timeout: 30,
    immediate_upload: true,
    batch_size: 100,
    interval: 5,
    retry_times: 3,
    retry_interval: 5,
    tags: ''
  }
  showChannelDialog.value = true
}

const handleEditChannel = (channel: ChannelListItem) => {
  const fullChannel = channelStore.getChannelById(channel.id)
  if (!fullChannel) return
  
  isEditing.value = true
  editingId.value = channel.id
  channelForm.value = {
    id: channel.id,
    name: channel.name,
    description: fullChannel.description || '',
    enabled: channel.enabled,
    protocol: channel.protocol,
    host: fullChannel.connection.broker || fullChannel.connection.remote_host || '',
    port: fullChannel.connection.port || fullChannel.connection.remote_port || 1883,
    username: fullChannel.connection.username || '',
    password: '',
    client_id: fullChannel.connection.client_id || '',
    topic: fullChannel.connection.topic || '',
    qos: fullChannel.connection.qos || 0,
    keepalive: fullChannel.connection.keepalive || 60,
    clean_session: fullChannel.connection.clean_session ?? true,
    adapter: fullChannel.adapter.adapter || 'standard',
    adapter_config: JSON.stringify(fullChannel.adapter.config || {}, null, 2),
    command_topic: fullChannel.connection.command_topic || '',
    publish_mode: fullChannel.connection.publish_mode || 'single',
    command_timeout: fullChannel.connection.command_timeout || 30,
    local_port: fullChannel.connection.local_port || 8888,
    remote_host: fullChannel.connection.remote_host || '127.0.0.1',
    remote_port: fullChannel.connection.remote_port || 9000,
    reconnect_interval: fullChannel.connection.reconnect_interval || 5,
    mapping_config: JSON.stringify(fullChannel.adapter.mapping_config || {}, null, 2),
    endpoint: fullChannel.connection.endpoint || '',
    method: fullChannel.connection.method || 'POST',
    headers: JSON.stringify(fullChannel.adapter.headers || {}, null, 2),
    timeout: fullChannel.connection.timeout || 30,
    immediate_upload: fullChannel.upload_strategy.immediate_upload,
    batch_size: fullChannel.upload_strategy.batch_size,
    interval: fullChannel.upload_strategy.interval,
    retry_times: fullChannel.upload_strategy.retry_times,
    retry_interval: fullChannel.upload_strategy.retry_interval || 5,
    tags: (fullChannel.tags || []).join(', ')
  }
  
  try {
    const config = JSON.parse(channelForm.value.adapter_config || '{}')
    productKey.value = config.productKey || ''
  } catch {
    productKey.value = ''
  }
  
  showChannelDialog.value = true
}

const buildChannelConfig = (): NorthChannelConfig => {
  const connection: any = {}
  let adapterConfig: any = {}
  let adapterType = 'default'
  
  if (channelForm.value.protocol === 'mqtt') {
    connection.broker = channelForm.value.host
    connection.port = channelForm.value.port
    if (channelForm.value.username) connection.username = channelForm.value.username
    if (channelForm.value.password) connection.password = channelForm.value.password
    connection.client_id = channelForm.value.client_id
    connection.topic = channelForm.value.topic
    connection.qos = channelForm.value.qos
    connection.keepalive = channelForm.value.keepalive
    connection.clean_session = channelForm.value.clean_session
    if (channelForm.value.command_topic) connection.command_topic = channelForm.value.command_topic
    if (channelForm.value.publish_mode) connection.publish_mode = channelForm.value.publish_mode
    if (channelForm.value.command_timeout) connection.command_timeout = channelForm.value.command_timeout
    
    adapterType = 'mqtt'
    
    if (channelForm.value.adapter) {
      adapterConfig.adapter = channelForm.value.adapter
    }
    try {
      const adapterConfigObj = JSON.parse(channelForm.value.adapter_config)
      if (Object.keys(adapterConfigObj).length > 0) {
        adapterConfig.config = adapterConfigObj
      }
    } catch (e) {
      console.error('Invalid adapter config JSON:', e)
    }
  } else if (channelForm.value.protocol === 'xnc') {
    connection.local_port = channelForm.value.local_port
    connection.remote_host = channelForm.value.remote_host
    connection.remote_port = channelForm.value.remote_port
    connection.reconnect_interval = channelForm.value.reconnect_interval
    
    adapterType = 'xnc_protobuf'
    
    try {
      const mappingConfig = JSON.parse(channelForm.value.mapping_config)
      if (Object.keys(mappingConfig).length > 0) {
        adapterConfig.mapping_config = mappingConfig
      }
    } catch (e) {
      console.error('Invalid mapping config JSON:', e)
    }
  } else if (channelForm.value.protocol === 'http') {
    connection.endpoint = channelForm.value.endpoint
    connection.method = channelForm.value.method
    connection.timeout = channelForm.value.timeout
    if (channelForm.value.username) connection.username = channelForm.value.username
    if (channelForm.value.password) connection.password = channelForm.value.password
    
    adapterType = 'http'
    
    try {
      const headers = JSON.parse(channelForm.value.headers)
      if (Object.keys(headers).length > 0) {
        adapterConfig.headers = headers
      }
    } catch (e) {
      console.error('Invalid headers JSON:', e)
    }
  }
  
  const config: any = {
    id: channelForm.value.id,
    name: channelForm.value.name,
    enabled: channelForm.value.enabled,
    protocol: channelForm.value.protocol,
    connection,
    adapter: {
      type: adapterType,
      ...adapterConfig
    },
    upload_strategy: {
      immediate_upload: channelForm.value.immediate_upload,
      batch_size: channelForm.value.batch_size,
      interval: channelForm.value.interval,
      retry_times: channelForm.value.retry_times,
      retry_interval: channelForm.value.retry_interval
    }
  }
  
  if (channelForm.value.description) {
    config.description = channelForm.value.description
  }
  
  if (channelForm.value.tags) {
    config.tags = channelForm.value.tags.split(',').map(t => t.trim()).filter(Boolean)
  }
  
  return config
}

const handleSaveChannel = async () => {
  if (!channelFormRef.value) return
  try {
    await channelFormRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const config = buildChannelConfig()
    
    if (isEditing.value) {
      await channelStore.updateChannel(editingId.value, config)
      ElMessage.success(t('channels.channelUpdated'))
    } else {
      await channelStore.createChannel(config)
      ElMessage.success(t('channels.channelCreated'))
    }
    showChannelDialog.value = false
  } catch (e: unknown) {
    const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : t('common.unknownError'))
    ElMessage.error(isEditing.value ? t('channels.updateFailed', { message: detail }) : t('channels.createFailed', { message: detail }))
  } finally {
    saving.value = false
  }
}

const handleDeleteChannel = (channel: ChannelListItem) => {
  ElMessageBox.confirm(
    t('channels.deleteConfirmMessage', { name: channel.name, id: channel.id }),
    t('channels.deleteConfirmTitle'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    }
  ).then(async () => {
    try {
      await channelStore.deleteChannel(channel.id)
      if (selectedChannelId.value === channel.id) {
        selectedChannelId.value = null
      }
      ElMessage.success(t('channels.channelDeleted'))
    } catch (e: unknown) {
      ElMessage.error(t('channels.deleteFailed', { message: e instanceof Error ? e.message : t('common.unknownError') }))
    }
  }).catch(() => {})
}

const handleTestConnection = async (id: string) => {
  try {
    ElMessage.info(t('channels.testingConnection'))
    const result = await channelStore.testConnection(id)
    if (result.success) {
      ElMessage.success(t('channels.connectionSuccess', { latency: result.latency }))
    } else {
      ElMessage.error(t('channels.connectionFailed', { message: result.message }))
    }
  } catch (e: unknown) {
    ElMessage.error(t('channels.testFailed', { message: e instanceof Error ? e.message : t('common.unknownError') }))
  }
}

const handleRestartChannel = async (id: string) => {
  try {
    await channelStore.restartChannel(id)
    ElMessage.success(t('channels.channelRestarted'))
  } catch (e: unknown) {
    ElMessage.error(t('channels.restartFailed', { message: e instanceof Error ? e.message : t('common.unknownError') }))
  }
}

const handleViewDetails = (id: string) => {
  selectedChannelId.value = id
}

const handleExportYaml = async () => {
  try {
    console.log('开始导出通道...')
    const result = await channelApi.exportChannels()
    console.log('导出结果:', result)
    
    const channels = result.channels || []
    
    if (channels.length === 0) {
      ElMessage.warning(t('channels.noExportableChannels'))
      return
    }
    
    const content = yaml.dump({ channels }, { 
      indent: 2, 
      lineWidth: 120,
      noRefs: true,
      sortKeys: false
    })
    const blob = new Blob([content], { type: 'text/yaml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `xagent-channels-${new Date().toISOString().slice(0, 10)}.yaml`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(t('channels.exportSuccess', { count: channels.length }))
  } catch (e: unknown) {
    console.error('导出失败:', e)
    if (e instanceof Error) {
      console.error('错误详情:', e.message)
      console.error('错误堆栈:', e.stack)
    }
    const errorMsg = e instanceof Error ? e.message : t('common.unknownError')
    ElMessage.error(t('channels.exportFailed', { message: errorMsg }))
  }
}

const importFileRef = ref<HTMLInputElement | null>(null)

const handleImportYaml = () => {
  importFileRef.value?.click()
}

const handleImportFileChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  try {
    const text = await file.text()
    const parsed = yaml.load(text) as { channels?: NorthChannelConfig[] }
    if (!parsed.channels || !Array.isArray(parsed.channels)) {
      ElMessage.error(t('channels.invalidYaml'))
      return
    }

    const channels = parsed.channels
    await ElMessageBox.confirm(
      t('channels.importConfirmMessage', { count: channels.length }),
      t('channels.importConfirmTitle'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'info' }
    )

    const result = await channelApi.importChannels({ channels: parsed.channels }, false)
    if (result.failed > 0) {
      ElMessage.warning(t('channels.importPartialSuccess', { success: result.succeeded, fail: result.failed }))
    } else {
      ElMessage.success(t('channels.importSuccess', { count: result.succeeded }))
    }
    await channelStore.fetchChannels()
  } catch (e: unknown) {
    if ((e as any) !== 'cancel') {
      ElMessage.error(t('channels.importFailed', { message: e instanceof Error ? e.message : t('common.unknownError') }))
    }
  }
}

const selectedChannel = computed(() => {
  if (!selectedChannelId.value) return null
  return channelStore.getChannelById(selectedChannelId.value)
})

// 格式化数字（添加千分位）
const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toLocaleString()
}

onMounted(async () => {
  await channelStore.fetchChannels()
})
</script>

<style scoped>
.channels-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 配置卡片样式 */
.config-card {
  margin-bottom: 16px;
  border: 1px solid var(--border-base);
}

.config-card.optional {
  border-color: var(--border-base);
  background: var(--bg-hover);
}

.config-card :deep(.el-card__header) {
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-base);
}

.config-card :deep(.el-card__body) {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

/* 折叠面板样式 */
.config-card :deep(.el-collapse) {
  border: none;
}

.config-card :deep(.el-collapse-item__header) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-base);
  border-radius: 4px;
  padding: 0 12px;
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.config-card :deep(.el-collapse-item__wrap) {
  border: 1px solid var(--border-base);
  border-top: none;
  border-radius: 0 0 4px 4px;
}

.config-card :deep(.el-collapse-item__content) {
  padding: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--bg-container);
  border-radius: 8px;
  box-shadow: var(--shadow-light);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-search {
  width: 250px;
}

.toolbar-filter {
  width: 120px;
}

.toolbar-stats {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-left: 8px;
  padding-left: 12px;
  border-left: 1px solid var(--border-light);
}

.stat-item {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-divider {
  color: var(--border-base);
  font-size: 14px;
  margin: 0 2px;
}

.stat-online .stat-value {
  color: var(--color-success);
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.main-content {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.main-content.compact-mode {
  flex-direction: column;
}

.compact-tabs {
  display: flex;
  background: var(--bg-container);
  border-radius: 8px;
  padding: 4px;
  gap: 4px;
  flex-shrink: 0;
  box-shadow: var(--shadow-light);
}

.compact-tab {
  flex: 1;
  padding: 12px 16px;
  text-align: center;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  background: transparent;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.compact-tab:hover {
  background: var(--bg-hover);
}

.compact-tab.active {
  background: var(--color-primary);
  color: var(--text-white);
}

.compact-tab.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tab-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-tab:not(.active) .tab-badge {
  background: var(--color-info-light, #e6f7ff);
  color: var(--color-info, #409eff);
}

.compact-panel {
  flex: 1;
  background: var(--bg-container);
  border-radius: 8px;
  box-shadow: var(--shadow-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.channel-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  align-content: start;
}

.channel-card-compact {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--border-base);
  background: var(--bg-container);
  cursor: pointer;
  transition: all 0.2s ease;
}

.channel-card-compact:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px var(--color-primary-light);
}

.channel-card-compact.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

.channel-card-compact.offline {
  opacity: 0.7;
}

.channel-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.channel-card-status {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-danger-light);
  color: var(--color-danger);
}

.channel-card-status.online {
  background: var(--color-success-light);
  color: var(--color-success);
}

.channel-card-info {
  flex: 1;
  min-width: 0;
}

.channel-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.channel-card-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
}

.stat-mini {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-mini-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.stat-mini-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.channel-card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.action-buttons {
  display: flex;
  gap: 4px;
}

.panel-header-left {
  display: flex;
  align-items: center;
}

.channel-list-panel {
  width: 320px;
  min-width: 260px;
  flex-shrink: 0;
  background: var(--bg-container);
  border-radius: 8px;
  box-shadow: var(--shadow-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.channel-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.channel-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.channel-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 8px;
  border: 1px solid transparent;
}

.channel-item:hover {
  background: var(--bg-hover);
}

.channel-item.selected {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
}

.channel-item.offline {
  opacity: 0.7;
}

.channel-item-status {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-danger-light);
  color: var(--color-danger);
}

.channel-item-status.online {
  background: var(--color-success-light);
  color: var(--color-success);
}

.channel-item-content {
  flex: 1;
  min-width: 0;
}

.channel-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.channel-item-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-item-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.channel-item-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.more-btn {
  padding: 4px;
  border-radius: 4px;
}

.more-btn:hover {
  background: var(--bg-hover);
}

.details-panel {
  flex: 1;
  background: var(--bg-container);
  border-radius: 8px;
  box-shadow: var(--shadow-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.empty-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--border-base);
}

.empty-details p {
  margin-top: 16px;
  font-size: 14px;
}

.details-actions {
  display: flex;
  gap: 8px;
}

.channel-details-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 标题栏状态信息 */
.header-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 12px;
}

.header-info .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger);
  flex-shrink: 0;
}

.header-info .status-dot.online {
  background: var(--color-success);
}

.protocol-tag {
  padding: 2px 8px;
  background: var(--color-info-light, #ecf5ff);
  color: var(--color-info, #409eff);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

/* 统计区域 - 简约风格 */
.stats-dashboard {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-container);
  border: 1px solid var(--border-base);
  border-radius: 8px;
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.upload-icon {
  background: var(--color-info-light, #ecf5ff);
  color: var(--color-info, #409eff);
}

.success-icon {
  background: var(--color-success-light, #f0f9eb);
  color: var(--color-success);
}

.backlog-icon {
  background: var(--color-warning-light, #fdf6ec);
  color: var(--color-warning);
}

.total-icon {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.stat-content {
  flex: 1;
}

.stat-content .stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-content .stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* 连接配置区域 */
.config-section {
  background: var(--bg-container);
  border-radius: 8px;
  border: 1px solid var(--border-base);
  overflow: hidden;
}

.section-title {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border-base);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1px;
  background: var(--border-light);
}

.config-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-container);
  min-height: 40px;
}

.config-item.full-width {
  grid-column: span 2;
}

.config-label {
  width: 80px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.config-value {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
}

.config-value.code {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

.config-value .muted {
  color: var(--text-secondary);
}

/* 适配器配置 */
.adapter-config {
  border-top: 1px solid var(--border-base);
  padding: 12px 16px;
}

.adapter-config-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.json-config {
  margin: 0;
  padding: 12px;
  background: var(--code-bg, #1e1e1e);
  color: var(--text-primary);
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  border: 1px solid var(--border-base);
}

/* 折叠面板 */
.detail-collapse {
  border: 1px solid var(--border-base);
  border-radius: 8px;
  overflow: hidden;
}

.detail-collapse :deep(.el-collapse-item__header) {
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border-base);
  padding: 0 16px;
  height: 42px;
  line-height: 42px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.detail-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.detail-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.description-text {
  margin: 0;
  padding: 16px;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
}

/* 映射配置帮助 */
.mapping-help {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.mapping-help-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.detail-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--text-primary);
}

.statistics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}

.stat-box {
  text-align: center;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.stat-box-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: 4px;
}

.stat-box-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-secondary);
}

.loading-state p {
  margin-top: 12px;
  font-size: 14px;
}

.empty-state {
  display: flex;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-secondary);
  font-size: 14px;
}

@media (max-width: 1200px) {
  .toolbar-search {
    width: 200px;
  }

  .channel-list-panel {
    width: 280px;
    min-width: 240px;
  }
}

@media (max-width: 1024px) {
  .toolbar-search {
    width: 180px;
  }

  .toolbar-filter {
    width: 110px;
  }
}

@media (max-width: 900px) {
  .main-content {
    flex-direction: column;
  }

  .channel-list-panel {
    width: 100%;
    min-width: 0;
    max-height: 280px;
  }

  .details-panel {
    min-height: 300px;
    flex: 1;
  }

  .toolbar-search {
    width: 100%;
    order: 1;
  }

  .toolbar-filter {
    width: 140px;
    order: 2;
  }

  .toolbar-stats {
    order: 3;
    margin-left: 0;
    padding-left: 0;
    border-left: none;
  }

  .toolbar-right {
    order: 4;
    margin-left: auto;
  }

  /* 详情页响应式 */
  .stats-dashboard {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-content .stat-value {
    font-size: 18px;
  }

  .config-grid {
    grid-template-columns: 1fr;
  }

  .config-item.full-width {
    grid-column: span 1;
  }

  .header-info {
    display: none;
  }
}

@media (max-width: 600px) {
  .toolbar {
    padding: 10px 12px;
  }

  .toolbar-search {
    width: 100%;
  }

  .toolbar-filter {
    width: 100%;
  }

  .toolbar-stats {
    width: 100%;
    justify-content: center;
  }

  .channel-list-panel {
    max-height: 220px;
  }

  .channel-item {
    padding: 10px;
  }

  .channel-item-meta {
    flex-direction: column;
    gap: 2px;
  }
}

@media (pointer: coarse) {
  .channel-item {
    padding: 14px 12px;
    min-height: 56px;
  }

  .channel-item-actions {
    gap: 8px;
  }

  .more-btn {
    padding: 8px;
    min-width: 36px;
    min-height: 36px;
  }

  .channel-item-status {
    width: 36px;
    height: 36px;
  }

  .el-button {
    min-height: 36px;
  }
}

@media (max-width: 1024px) {
  .channel-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 8px;
    padding: 8px;
  }

  .channel-card-compact {
    padding: 12px;
  }

  .compact-tab {
    padding: 8px 12px;
    font-size: 13px;
  }

  .panel-header {
    padding: 8px 12px;
  }

  .toolbar {
    padding: 10px 12px;
    gap: 8px;
  }

  .toolbar-right {
    flex-wrap: wrap;
  }
}

@media (max-height: 700px) {
  .toolbar {
    padding: 8px 12px;
    gap: 8px;
  }

  .compact-tabs {
    padding: 2px;
    gap: 2px;
  }

  .compact-tab {
    padding: 6px 10px;
    font-size: 13px;
  }

  .channel-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 6px;
    padding: 6px;
  }

  .channel-card-compact {
    padding: 10px;
  }

  .channel-card-header {
    margin-bottom: 6px;
  }

  .panel-header {
    padding: 6px 10px;
    min-height: 36px;
  }

  .panel-title {
    font-size: 14px;
  }

  .loading-state {
    padding: 30px 0;
  }

  .empty-state {
    padding: 30px 0;
  }
}

/* 表单辅助样式 */
.full-width {
  width: 100%;
}

.form-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.unit-hint {
  margin-left: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.option-desc {
  float: right;
  color: var(--text-secondary);
  font-size: 12px;
}

.danger-text {
  color: var(--color-danger);
}

.alert-with-margin {
  margin-bottom: 12px;
}
</style>
