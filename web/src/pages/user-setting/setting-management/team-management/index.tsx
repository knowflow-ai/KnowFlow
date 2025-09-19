import { useTranslate } from '@/hooks/common-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import request from '@/utils/request';
import {
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Pagination,
  Popconfirm,
  Radio,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import styles from './index.less';

const { Option } = Select;

interface TeamData {
  id: string;
  name: string;
  ownerName: string;
  memberCount: number;
  createTime: string;
  updateTime: string;
}

interface TeamMember {
  userId: number | string;
  username: string;
  role: string;
  joinTime: string;
}

interface UserData {
  id: string;
  username: string;
  email: string;
}

interface Role {
  id: string;
  name: string;
  code: string;
  description: string;
}

const TeamManagementPage = () => {
  const { t } = useTranslate('setting');

  // 登录用户信息
  const { data: userInfo } = useFetchUserInfo();
  const userId = userInfo?.id;
  const [loading, setLoading] = useState(false);
  const [memberLoading, setMemberLoading] = useState(false);
  const [userLoading, setUserLoading] = useState(false);

  const [teamData, setTeamData] = useState<TeamData[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [userList, setUserList] = useState<UserData[]>([]);
  const [availableUsers, setAvailableUsers] = useState<UserData[]>([]);

  const [memberModalVisible, setMemberModalVisible] = useState(false);
  const [addMemberModalVisible, setAddMemberModalVisible] = useState(false);
  const [roleModalVisible, setRoleModalVisible] = useState(false);
  const [currentTeam, setCurrentTeam] = useState<TeamData | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [selectedRole, setSelectedRole] = useState<string>('normal');
  const [teamRoles, setTeamRoles] = useState<Role[]>([]);
  const [teamRolesMap, setTeamRolesMap] = useState<Record<string, Role>>({});

  const [searchForm] = Form.useForm();
  const [addMemberForm] = Form.useForm();
  const [roleForm] = Form.useForm();
  const [teamForm] = Form.useForm();
  const [teamModalVisible, setTeamModalVisible] = useState(false);

  // 角色优先级映射
  const rolePriorityMap: Record<string, { priority: number; color: string }> = {
    super_admin: { priority: 1, color: '#f50' }, // 超级管理员 - 红色
    admin: { priority: 2, color: '#722ed1' }, // 管理员 - 紫色
    editor: { priority: 3, color: '#1890ff' }, // 编辑者 - 蓝色
    viewer: { priority: 4, color: '#52c41a' }, // 查看者 - 绿色
    user: { priority: 5, color: '#d9d9d9' }, // 用户 - 灰色
  };

  // 获取最高优先级角色
  const getHighestPriorityRole = (teamRolesList: Role[]): Role | null => {
    if (!teamRolesList || teamRolesList.length === 0) return null;

    return teamRolesList.reduce((highest, current) => {
      const currentPriority = rolePriorityMap[current.code]?.priority || 999;
      const highestPriority = rolePriorityMap[highest.code]?.priority || 999;
      return currentPriority < highestPriority ? current : highest;
    });
  };

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  useEffect(() => {
    loadTeamData();
    loadUserList();
  }, [pagination.current, pagination.pageSize]);

  const loadTeamData = async () => {
    setLoading(true);
    try {
      const values = searchForm.getFieldsValue();
      const res = await request.get('/api/knowflow/v1/teams', {
        params: {
          currentPage: pagination.current,
          size: pagination.pageSize,
          name: values.name,
          ownerName: values.ownerName,
        },
      });
      const data = res?.data?.data || {};
      const list = data.list || [];
      setTeamData(list);
      setPagination((prev) => ({ ...prev, total: data.total || 0 }));

      // 拉取每个团队的角色，构建映射
      const rolesMap: Record<string, Role> = {};
      await Promise.all(
        (list as TeamData[]).map(async (team) => {
          try {
            const r = await request.get(
              `/api/knowflow/v1/teams/${team.id}/roles`,
            );
            const teamRolesList = r?.data?.data ?? [];

            // 团队角色API返回的是TeamRole对象，需要转换为Role格式
            if (teamRolesList.length > 0) {
              // 获取可分配的角色信息用于匹配
              const rolesRes = await request.get(
                '/api/knowflow/v1/rbac/assignable-roles',
              );
              const allRoles = rolesRes?.data?.data || [];

              // 根据role_code匹配角色信息
              const teamRole = teamRolesList[0]; // 取第一个角色
              const matchedRole = allRoles.find(
                (role: Role) => role.code === teamRole.role_code,
              );
              if (matchedRole) {
                rolesMap[team.id] = matchedRole;
              }
            }
          } catch (e) {
            // 错误情况下不设置角色
          }
        }),
      );
      setTeamRolesMap(rolesMap);
    } catch (error) {
      message.error('加载团队数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadUserList = async () => {
    setUserLoading(true);
    try {
      const res = await request.get('/api/knowflow/v1/users', {
        params: {
          currentPage: 1,
          size: 1000, // Get all users for selection
        },
      });
      const data = res?.data?.data || {};
      const users = (data.list || []).map((user: any) => ({
        id: user.id,
        username: user.username,
        email: user.email, // 添加邮箱字段
      }));
      setUserList(users);
    } catch (error) {
      message.error('加载用户列表失败');
    } finally {
      setUserLoading(false);
    }
  };

  const loadTeamMembers = async (teamId: string) => {
    setMemberLoading(true);
    try {
      const res = await request.get(`/api/knowflow/v1/teams/${teamId}/members`);
      const data = res?.data?.data || [];
      setTeamMembers(data);

      // 更新可添加的用户列表
      const memberUserIds = new Set(
        data.map((member: TeamMember) => member.userId),
      );
      const available = userList.filter((user) => !memberUserIds.has(user.id));
      setAvailableUsers(available);
    } catch (error) {
      message.error('加载团队成员失败');
      setTeamMembers([]);
    } finally {
      setMemberLoading(false);
    }
  };

  const handleSearch = async () => {
    const values = searchForm.getFieldsValue();
    console.log('搜索条件:', values);
    loadTeamData();
  };

  const handleReset = () => {
    searchForm.resetFields();
    loadTeamData();
  };

  const handleCreateTeam = () => {
    teamForm.resetFields();
    // 默认设置当前用户为负责人
    if (userId) {
      teamForm.setFieldsValue({ owner_id: userId });
    }
    setTeamModalVisible(true);
  };

  const handleTeamSubmit = async () => {
    try {
      const values = await teamForm.validateFields();
      setLoading(true);
      await request.post('/api/knowflow/v1/teams', {
        data: {
          name: values.name,
          owner_id: values.owner_id,
          description: values.description || '',
        },
      });
      message.success('创建团队成功');
      setTeamModalVisible(false);
      await loadTeamData();
    } catch (error) {
      message.error('创建团队失败');
    } finally {
      setLoading(false);
    }
  };

  const handleManageMembers = (team: TeamData) => {
    setCurrentTeam(team);
    setMemberModalVisible(true);
    loadTeamMembers(team.id);
  };

  const handleTeamRoleManagement = async (team: TeamData) => {
    setCurrentTeam(team);
    try {
      // 获取可分配的角色（根据当前用户权限过滤）
      const rolesRes = await request.get(
        '/api/knowflow/v1/rbac/assignable-roles',
      );
      setTeamRoles(rolesRes?.data?.data || []);

      // 获取团队当前已分配角色，用于预选中
      const assignedRes = await request.get(
        `/api/knowflow/v1/teams/${team.id}/roles`,
      );
      const teamRolesList = assignedRes?.data?.data ?? [];

      let selectedRoleId = '';
      if (teamRolesList.length > 0) {
        // 根据role_code找到对应的角色ID
        const teamRole = teamRolesList[0];
        const allRoles = rolesRes?.data?.data || [];
        const matchedRole = allRoles.find(
          (role: Role) => role.code === teamRole.role_code,
        );
        if (matchedRole) {
          selectedRoleId = matchedRole.id;
        }
      }

      roleForm.setFieldsValue({
        roleId: selectedRoleId,
      });

      setRoleModalVisible(true);
    } catch (error: any) {
      message.error('获取团队角色失败');
    }
  };

  const handleRoleSubmit = async () => {
    try {
      const values = await roleForm.validateFields();
      setLoading(true);

      const selected = teamRoles.find((r) => r.id === values.roleId);
      if (!selected) {
        message.error('选择的角色不存在');
        return;
      }

      // 获取当前用户信息作为granted_by
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      const grantedBy = userInfo.id || 'system';

      await request.post(`/api/knowflow/v1/teams/${currentTeam?.id}/roles`, {
        data: {
          role_code: selected.code,
          resource_type: 'system', // 默认为系统级别角色
          resource_id: null,
          tenant_id: 'default',
          granted_by: grantedBy,
        },
        headers: {
          'Content-Type': 'application/json',
        },
      });
      message.success('团队角色配置成功');
      setRoleModalVisible(false);
      await loadTeamData();
    } catch (error: any) {
      message.error('团队角色配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAddMember = () => {
    setSelectedUser('');
    setSelectedRole('normal');
    addMemberForm.resetFields();
    setAddMemberModalVisible(true);
  };

  const handleAddMemberSubmit = async () => {
    try {
      const values = await addMemberForm.validateFields();
      console.log('表单验证结果:', values); // 调试日志
      console.log('当前用户列表:', userList); // 调试日志
      setMemberLoading(true);
      if (currentTeam) {
        // 根据 knowflow 实现，使用邮箱查找用户
        const selectedUser = userList.find((user) => user.id === values.userId);
        console.log('选中的用户:', selectedUser); // 调试日志

        if (!selectedUser) {
          message.error('用户不存在');
          return;
        }

        if (!selectedUser.email && !selectedUser.username) {
          message.error('用户邮箱信息缺失');
          return;
        }

        // 参考 knowflow 的请求格式：通过邮箱添加用户到租户
        const requestData = {
          email: selectedUser.email || selectedUser.username, // 优先使用邮箱，后备使用用户名
        };

        console.log('实际发送的请求数据:', requestData);

        if (!requestData.email) {
          message.error('无法获取用户邮箱信息');
          return;
        }

        // 使用 knowflow 的 API 端点格式，直接传递数据
        const response = await request.post(
          `/v1/tenant/${currentTeam.id}/user`,
          {
            data: requestData,
          },
        );

        message.success('添加成员成功');
        setAddMemberModalVisible(false);
        await loadTeamMembers(currentTeam.id);
        await loadTeamData(); // Refresh team list to update member counts
      }
    } catch (error) {
      console.error('添加成员错误:', error); // 调试日志
      message.error(
        `添加团队成员失败: ${error instanceof Error ? error.message : JSON.stringify(error)}`,
      );
    } finally {
      setMemberLoading(false);
    }
  };

  const handleRemoveMember = async (member: TeamMember) => {
    if (!currentTeam) return;

    setMemberLoading(true);
    try {
      await request.delete(
        `/api/knowflow/v1/teams/${currentTeam.id}/members/${member.userId}`,
      );
      message.success('移除成员成功');
      await loadTeamMembers(currentTeam.id);
      await loadTeamData(); // Refresh team list to update member counts
    } catch (error) {
      message.error('移除成员失败');
    } finally {
      setMemberLoading(false);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    setLoading(true);
    try {
      await request.delete(`/api/knowflow/v1/teams/${teamId}`);
      message.success('删除团队成功');
      await loadTeamData();
    } catch (error) {
      message.error('删除团队失败');
    } finally {
      setLoading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的团队');
      return;
    }
    setLoading(true);
    try {
      await Promise.all(
        selectedRowKeys.map((id) =>
          request.delete(`/api/knowflow/v1/teams/${id}`),
        ),
      );
      setSelectedRowKeys([]);
      message.success(`成功删除 ${selectedRowKeys.length} 个团队`);
      await loadTeamData();
    } catch (error) {
      message.error('批量删除失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '团队名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
      render: (text: string) => (
        <Space>
          <TeamOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '负责人',
      dataIndex: 'ownerName',
      key: 'ownerName',
      width: 120,
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '成员数量',
      dataIndex: 'memberCount',
      key: 'memberCount',
      width: 100,
      render: (count: number) => <Tag color="green">{count}人</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'createTime',
      key: 'createTime',
      width: 150,
    },
    {
      title: '更新时间',
      dataIndex: 'updateTime',
      key: 'updateTime',
      width: 150,
    },
    {
      title: '角色',
      key: 'roles',
      width: 100,
      render: (_: any, record: TeamData) => {
        const role =
          teamRolesMap[record.id] ||
          ({ id: '', name: '用户', code: 'user', description: '' } as Role);

        const roleConfig = rolePriorityMap[role.code] || {
          priority: 999,
          color: '#d9d9d9',
        };
        return <Tag color={roleConfig.color}>{role.name || role.code}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right' as const,
      width: 280,
      render: (_: any, record: TeamData) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<UserOutlined />}
            onClick={() => handleManageMembers(record)}
          >
            成员管理
          </Button>
          <Button
            type="link"
            size="small"
            icon={<SettingOutlined />}
            onClick={() => handleTeamRoleManagement(record)}
          >
            角色配置
          </Button>
          <Popconfirm
            title="确定删除这个团队吗？"
            onConfirm={() => handleDeleteTeam(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const memberColumns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (text: string) => (
        <Space>
          <UserOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => (
        <Tag color={role === 'owner' ? 'red' : 'blue'}>
          {role === 'owner' ? '拥有者' : '普通成员'}
        </Tag>
      ),
    },
    {
      title: '加入时间',
      dataIndex: 'joinTime',
      key: 'joinTime',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: TeamMember) => (
        <Popconfirm
          title={`确认将 ${record.username} 从团队中移除吗？`}
          onConfirm={() => handleRemoveMember(record)}
          disabled={record.role === 'owner'}
        >
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            disabled={record.role === 'owner'}
          >
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const handleTableChange = (page: number, pageSize: number) => {
    setPagination((prev) => ({ ...prev, current: page, pageSize }));
  };

  return (
    <div className={styles.teamManagementWrapper}>
      {/* 搜索区域 */}
      <Card className={styles.searchCard} size="small">
        <Form form={searchForm} layout="inline">
          <Form.Item name="name" label="团队名称">
            <Input placeholder="请输入团队名称" allowClear />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={handleSearch}
                loading={loading}
              >
                搜索
              </Button>
              <Button icon={<ReloadOutlined />} onClick={handleReset}>
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {/* 团队列表 */}
      <Card className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreateTeam}
            >
              新建团队
            </Button>
            <Popconfirm
              title={`确定删除选中的 ${selectedRowKeys.length} 个团队吗？`}
              onConfirm={handleBatchDelete}
              disabled={selectedRowKeys.length === 0}
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                disabled={selectedRowKeys.length === 0}
              >
                批量删除
              </Button>
            </Popconfirm>
          </Space>
          <Button icon={<ReloadOutlined />} onClick={loadTeamData}>
            刷新
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={teamData}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 970 }}
          rowSelection={{
            selectedRowKeys,
            onChange: (selectedRowKeys: React.Key[]) =>
              setSelectedRowKeys(selectedRowKeys as string[]),
          }}
        />

        <div className={styles.paginationWrapper}>
          <Pagination
            current={pagination.current}
            pageSize={pagination.pageSize}
            total={pagination.total}
            onChange={handleTableChange}
            showSizeChanger
            showQuickJumper
            showTotal={(total, range) =>
              `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
            }
          />
        </div>
      </Card>

      {/* 团队成员管理模态框 */}
      <Modal
        title={`${currentTeam?.name || ''} - 成员管理`}
        open={memberModalVisible}
        onCancel={() => setMemberModalVisible(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setMemberModalVisible(false)}>
            关闭
          </Button>,
        ]}
      >
        {currentTeam && (
          <div>
            <Descriptions
              className={styles.teamInfo}
              column={2}
              bordered
              size="small"
            >
              <Descriptions.Item label="团队名称">
                {currentTeam.name}
              </Descriptions.Item>
              <Descriptions.Item label="负责人">
                {currentTeam.ownerName}
              </Descriptions.Item>
            </Descriptions>

            <div className={styles.memberToolbar}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleAddMember}
                disabled={availableUsers.length === 0}
              >
                添加成员
              </Button>
            </div>

            <Table
              columns={memberColumns}
              dataSource={teamMembers}
              rowKey="userId"
              loading={memberLoading}
              pagination={false}
              size="small"
              locale={{
                emptyText: <Empty description="暂无成员数据" />,
              }}
            />
          </div>
        )}
      </Modal>

      {/* 添加成员模态框 */}
      <Modal
        title="添加团队成员"
        open={addMemberModalVisible}
        onOk={handleAddMemberSubmit}
        onCancel={() => setAddMemberModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
      >
        <Form form={addMemberForm} layout="vertical">
          <Form.Item
            name="userId"
            label="选择用户"
            rules={[{ required: true, message: '请选择用户' }]}
          >
            <Select
              placeholder={
                availableUsers.length > 0
                  ? '请选择用户'
                  : '(当前无可添加的用户)'
              }
              disabled={availableUsers.length === 0}
              loading={userLoading}
            >
              {availableUsers.map((user) => (
                <Option key={user.id} value={user.id}>
                  {user.username} ({user.email || '无邮箱'})
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            initialValue="normal"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Radio.Group>
              <Radio value="normal">普通成员</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>

      {/* 团队角色配置模态框 */}
      <Modal
        title={`${currentTeam?.name || ''} - 角色配置`}
        open={roleModalVisible}
        onOk={handleRoleSubmit}
        onCancel={() => setRoleModalVisible(false)}
        confirmLoading={loading}
      >
        <Form form={roleForm} layout="vertical">
          <Form.Item
            name="roleId"
            label="选择角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="请选择角色" style={{ width: '100%' }}>
              {teamRoles
                .filter((role: any) => role.code !== 'super_admin')
                .map((role: any) => (
                  <Select.Option key={role.id} value={role.id}>
                    {role.name} - {role.description}
                  </Select.Option>
                ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 新建团队模态框 */}
      <Modal
        title="新建团队"
        open={teamModalVisible}
        onOk={handleTeamSubmit}
        onCancel={() => setTeamModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
        width={500}
      >
        <Form form={teamForm} layout="vertical">
          <Form.Item
            name="name"
            label="团队名称"
            rules={[{ required: true, message: '请输入团队名称' }]}
          >
            <Input placeholder="请输入团队名称" />
          </Form.Item>
          <Form.Item
            name="owner_id"
            label="负责人"
            rules={[{ required: true, message: '请选择负责人' }]}
          >
            {userInfo?.is_superuser ? (
              <Select
                placeholder="请选择负责人"
                showSearch
                optionFilterProp="children"
                loading={userList.length === 0}
              >
                {userList.map((u) => (
                  <Option key={u.id} value={u.id}>
                    {u.username} ({u.email || '无邮箱'})
                  </Option>
                ))}
              </Select>
            ) : (
              <Select
                value={userId}
                disabled
                style={{ backgroundColor: '#f5f5f5' }}
              >
                <Option value={userId}>
                  {userInfo?.nickname || '当前管理员'}
                </Option>
              </Select>
            )}
          </Form.Item>
          <Form.Item name="description" label="团队描述">
            <Input.TextArea placeholder="请输入团队描述（可选）" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TeamManagementPage;
