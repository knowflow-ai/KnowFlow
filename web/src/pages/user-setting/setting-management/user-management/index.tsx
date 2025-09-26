import { useTranslate } from '@/hooks/common-hooks';
import request from '@/utils/request';
import {
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import styles from './index.less';

interface UserData {
  id: string;
  username: string;
  email: string;
  createTime: string;
  updateTime: string;
}

interface Role {
  id: string;
  name: string;
  code: string;
  description: string;
}

interface UserRole {
  id: string;
  name: string;
  code: string;
  description: string;
}

const UserManagementPage = () => {
  const { t } = useTranslate('setting');
  const [loading, setLoading] = useState(false);
  const [userData, setUserData] = useState<UserData[]>([]);
  const [userModalVisible, setUserModalVisible] = useState(false);
  const [resetPasswordModalVisible, setResetPasswordModalVisible] =
    useState(false);
  const [editingUser, setEditingUser] = useState<UserData | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string>('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [searchForm] = Form.useForm();
  const [userForm] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const [roleForm] = Form.useForm();
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [roleModalVisible, setRoleModalVisible] = useState(false);
  const [roles, setRoles] = useState<Role[]>([]);
  const [userRoles, setUserRoles] = useState<UserRole[]>([]);
  const [userRolesMap, setUserRolesMap] = useState<Record<string, UserRole>>(
    {},
  );

  // 角色优先级映射
  const rolePriorityMap: Record<string, { priority: number; color: string }> = {
    super_admin: { priority: 1, color: '#f50' }, // 超级管理员 - 红色
    admin: { priority: 2, color: '#722ed1' }, // 管理员 - 紫色
    editor: { priority: 3, color: '#1890ff' }, // 编辑者 - 蓝色
    viewer: { priority: 4, color: '#52c41a' }, // 查看者 - 绿色
    user: { priority: 5, color: '#d9d9d9' }, // 用户 - 灰色
  };

  // 获取用户角色（每个用户只有一个角色）
  const getUserRole = (userRolesList: UserRole[]): UserRole | null => {
    if (!userRolesList || userRolesList.length === 0) return null;
    // 直接返回第一个角色，因为每个用户只能有一个角色
    return userRolesList[0];
  };
  // 模拟用户数据
  // const mockUsers: UserData[] = [
  //   {
  //     id: '1',
  //     username: 'admin',
  //     email: 'admin@ragflow.io',
  //     nickname: '系统管理员',
  //     is_superuser: true,
  //     is_active: true,
  //     create_time: '2024-01-01 10:00:00',
  //     update_time: '2024-01-01 10:00:00',
  //   },
  //   {
  //     id: '2',
  //     username: 'user1',
  //     email: '541642069@qq.com',
  //     nickname: '普通用户1',
  //     is_superuser: false,
  //     is_active: true,
  //     create_time: '2024-01-02 10:00:00',
  //     update_time: '2024-01-02 10:00:00',
  //   },
  //   {
  //     id: '3',
  //     username: 'user2',
  //     email: '1124746174@qq.com',
  //     nickname: '普通用户2',
  //     is_superuser: false,
  //     is_active: true,
  //     create_time: '2024-01-03 10:00:00',
  //     update_time: '2024-01-03 10:00:00',
  //   },
  //   {
  //     id: '4',
  //     username: 'testuser',
  //     email: 'test@example.com',
  //     nickname: '测试用户',
  //     is_superuser: false,
  //     is_active: false,
  //     create_time: '2024-01-04 10:00:00',
  //     update_time: '2024-01-04 10:00:00',
  //   },
  // ];

  useEffect(() => {
    loadUserData();
  }, [pagination.current, pagination.pageSize]);

  const loadUserData = async () => {
    setLoading(true);
    try {
      const values = searchForm.getFieldsValue();
      const res = await request.get('/api/knowflow/v1/users', {
        params: {
          currentPage: pagination.current,
          size: pagination.pageSize,
          username: values.username,
          email: values.email,
        },
      });
      const data = res?.data?.data || {};
      const list = data.list || [];
      setUserData(list);
      setPagination((prev) => ({ ...prev, total: data.total || 0 }));

      // 使用批量接口获取所有用户的角色
      const rolesMap: Record<string, UserRole> = {};
      if (list.length > 0) {
        try {
          // 提取用户ID列表
          const userIds = list.map((u: UserData) => u.id);

          // 调用批量角色查询接口
          const batchRolesRes = await request.post(
            '/api/knowflow/v1/rbac/users/batch-roles',
            {
              data: {
                user_ids: userIds,
                tenant_id: 'default',
              },
            },
          );

          // 处理批量查询结果
          const userRolesData = batchRolesRes?.data?.user_roles || {};

          // 构建角色映射
          Object.entries(userRolesData).forEach(([userId, rolesList]) => {
            const userRole = getUserRole(rolesList as UserRole[]);
            if (userRole) {
              rolesMap[userId] = userRole;
            }
          });
        } catch (error) {
          console.error('批量获取用户角色失败:', error);
          // 批量接口失败时的降级处理（可选）
          // 可以选择静默失败，或者回退到单个查询
        }
      }
      setUserRolesMap(rolesMap);
    } catch (error) {
      message.error('加载用户数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    await loadUserData();
  };

  const handleReset = async () => {
    searchForm.resetFields();
    setPagination((prev) => ({ ...prev, current: 1 }));
    await loadUserData();
  };

  const handleCreateUser = () => {
    setEditingUser(null);
    userForm.resetFields();
    setUserModalVisible(true);
  };

  const handleEditUser = (user: UserData) => {
    setEditingUser(user);
    userForm.setFieldsValue(user);
    setUserModalVisible(true);
  };

  const handleDeleteUser = async (userId: string) => {
    setLoading(true);
    try {
      await request.delete(`/api/knowflow/v1/users/${userId}`);
      message.success('删除用户成功');
      await loadUserData();
    } catch (error) {
      message.error('删除用户失败');
    } finally {
      setLoading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的用户');
      return;
    }
    setLoading(true);
    try {
      await Promise.all(
        selectedRowKeys.map((id) =>
          request.delete(`/api/knowflow/v1/users/${id}`),
        ),
      );
      setSelectedRowKeys([]);
      message.success(`成功删除 ${selectedRowKeys.length} 个用户`);
      await loadUserData();
    } catch (error) {
      message.error('批量删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = (userId: string) => {
    setCurrentUserId(userId);
    passwordForm.resetFields();
    setResetPasswordModalVisible(true);
  };

  const handleAssignRole = async (user: UserData) => {
    setEditingUser(user);
    setCurrentUserId(user.id);
    try {
      // 获取可分配的角色（根据当前用户权限过滤）
      const rolesRes = await request.get(
        '/api/knowflow/v1/rbac/assignable-roles',
      );
      setRoles(rolesRes.data.data || []);

      // 获取用户当前角色（兼容不同返回结构）
      const userRolesRes = await request.get(
        `/api/knowflow/v1/rbac/users/${user.id}/roles`,
      );
      const rolesList =
        userRolesRes?.data?.data ?? userRolesRes?.data?.roles ?? [];
      setUserRoles(rolesList);

      roleForm.setFieldsValue({
        roleId: (rolesList || []).map((role: any) => role.id)[0],
      });
      setRoleModalVisible(true);
    } catch (error) {
      message.error('获取角色信息失败');
    }
  };

  // 移除查看权限相关逻辑（handleViewPermissions 已删除）

  const handleRoleSubmit = async () => {
    try {
      const values = await roleForm.validateFields();
      setLoading(true);

      // 修复：将选择的角色转换为后端需要的 role_code 字段，并通过 data 提交
      if (values.roleId) {
        const selectedRole = roles.find((role) => role.id === values.roleId);
        if (selectedRole) {
          await request.post(
            `/api/knowflow/v1/rbac/users/${currentUserId}/roles`,
            {
              data: {
                role_code: selectedRole.code,
              },
            },
          );
          message.success('角色分配成功');
          setRoleModalVisible(false);
          await loadUserData();
        } else {
          message.error('选择的角色不存在');
        }
      } else {
        message.warning('请选择要分配的角色');
      }
    } catch (error) {
      message.error('角色分配失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUserSubmit = async () => {
    try {
      const values = await userForm.validateFields();
      setLoading(true);
      if (editingUser) {
        if (editingUser.id) {
          const result = await request.put(
            `/api/knowflow/v1/users/${editingUser.id}`,
            {
              data: values,
            },
          );
          // 由于 getResponse: true，需要检查响应数据
          if (result?.data?.code === 0) {
            message.success('更新用户成功');
            setUserModalVisible(false);
            await loadUserData();
          }
        }
      } else {
        const result = await request.post('/api/knowflow/v1/users', {
          data: values,
        });
        // 由于 getResponse: true，需要检查响应数据
        if (result?.data?.code === 0) {
          message.success('创建用户成功');
          setUserModalVisible(false);
          await loadUserData();
        }
      }
    } catch (error) {
      // 错误已经由 request 拦截器显示，这里只记录日志
      console.error('操作失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async () => {
    try {
      const values = await passwordForm.validateFields();
      setLoading(true);
      await request.put(
        `/api/knowflow/v1/users/${currentUserId}/reset-password`,
        {
          data: { password: values.password },
        },
      );
      message.success('重置密码成功');
      setResetPasswordModalVisible(false);
    } catch (error) {
      message.error('重置密码失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 120,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      width: 180,
    },
    {
      title: '创建时间',
      dataIndex: 'createTime',
      key: 'createTime',
      width: 100,
    },
    {
      title: '更新时间',
      dataIndex: 'updateTime',
      key: 'updateTime',
      width: 120,
    },
    {
      title: '角色',
      key: 'roles',
      width: 100,
      render: (_: any, record: UserData) => {
        const role = userRolesMap[record.id];
        if (role === undefined) return <Tag color="#d9d9d9">用户</Tag>;
        if (!role) return <Tag color="#d9d9d9">用户</Tag>;

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
      width: 320,
      render: (_: any, record: UserData) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditUser(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            icon={<KeyOutlined />}
            onClick={() => handleResetPassword(record.id)}
          >
            重置密码
          </Button>
          <Button
            type="link"
            size="small"
            icon={<UserOutlined />}
            onClick={() => handleAssignRole(record)}
          >
            角色
          </Button>
          <Popconfirm
            title="确定删除这个用户吗？"
            onConfirm={() => handleDeleteUser(record.id)}
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

  const handleTableChange = (page: number, pageSize: number) => {
    setPagination((prev) => ({ ...prev, current: page, pageSize }));
  };

  return (
    <div className={styles.userManagementWrapper}>
      {/* 搜索区域 */}
      <Card className={styles.searchCard} size="small">
        <Form form={searchForm} layout="inline">
          <Form.Item name="username" label="用户名">
            <Input placeholder="请输入用户名" allowClear />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="请输入邮箱" allowClear />
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
      {/* 操作区域 */}
      <Card className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreateUser}
            >
              新建用户
            </Button>
            <Popconfirm
              title={`确定删除选中的 ${selectedRowKeys.length} 个用户吗？`}
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
          <Button icon={<ReloadOutlined />} onClick={loadUserData}>
            刷新
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={userData}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 940 }}
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
      {/* 角色分配模态框 */}
      <Modal
        title="分配角色"
        open={roleModalVisible}
        onOk={handleRoleSubmit}
        onCancel={() => setRoleModalVisible(false)}
        confirmLoading={loading}
      >
        <Form form={roleForm} layout="vertical">
          <Form.Item
            name="roleId"
            label="选择角色"
            rules={[{ required: true, message: '请选择一个角色' }]}
          >
            <Select placeholder="请选择角色" style={{ width: '100%' }}>
              {roles
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

      {/* 用户编辑/创建模态框 */}
      <Modal
        title={editingUser ? '编辑用户' : '新建用户'}
        open={userModalVisible}
        onOk={handleUserSubmit}
        onCancel={() => setUserModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
        width={500}
      >
        <Form form={userForm} layout="vertical">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入正确的邮箱格式' },
            ]}
          >
            <Input placeholder="请输入邮箱" disabled={!!editingUser} />
          </Form.Item>
          {!editingUser && (
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password placeholder="请输入密码" />
            </Form.Item>
          )}
        </Form>
      </Modal>
      {/* 重置密码模态框 */}
      <Modal
        title="重置密码"
        open={resetPasswordModalVisible}
        onOk={handlePasswordSubmit}
        onCancel={() => setResetPasswordModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item
            name="password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码长度至少6位' },
            ]}
          >
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="确认密码"
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagementPage;
