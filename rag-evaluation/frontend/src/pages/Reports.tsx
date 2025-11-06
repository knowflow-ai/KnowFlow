import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Typography,
  Row,
  Col,
  Statistic,
  Progress,
  Descriptions,
  Alert,
  Divider,
  Empty,
  Tooltip,
  Select,
  DatePicker,
  Tabs,
  List,
  Avatar,
  Badge,
  Spin,
  message,
  Collapse,
  Timeline,
  Rate,
  Modal,
} from 'antd';
import {
  FileTextOutlined,
  DownloadOutlined,
  ShareAltOutlined,
  PrinterOutlined,
    TrophyOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  RiseOutlined,
  FallOutlined,
  EyeOutlined,
  QuestionCircleOutlined,
  MessageOutlined,
  BulbOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { reportApi, datasetApi, chatApi } from '../services/evaluation';
import type { EvaluationReport as ApiReport, DatasetSample } from '../services/evaluation';
import { useBatchDelete } from '../hooks/useBatchDelete';
import { BatchActionBar } from '../components/BatchActionBar';

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;
const { Panel } = Collapse;

interface EvaluationReport {
  id: string;
  taskId: string;
  taskName: string;
  kbName: string;
  datasetName: string;
  overallScore: number;
  metricScores: {
    [key: string]: {
      mean: number;
      std: number;
      min: number;
      max: number;
    };
  };
  createdAt: string;
  duration: string;
  totalSamples: number;
  recommendations: string[];
  lowScoreSamples: Array<{
    question: string;
    score: number;
    issue: string;
  }>;
  detailed_scores?: Array<{
    user_input: string;
    actual_answer: string;
    expected_answer: string;
    contexts: string[];
    [key: string]: any;  // for metric scores
  }>;
}

interface MetricTrend {
  date: string;
  faithfulness: number;
  answerCorrectness: number;
  contextPrecision: number;
  contextRecall: number;
}

const Reports: React.FC = () => {
  // Helper functions
  const getMetricDisplayName = (metric: string) => {
    const metricNames: { [key: string]: string } = {
      answer_correctness: '答案正确性',
      faithfulness: '忠实度',
      context_precision: '上下文精准度',
      context_recall: '上下文召回率',
      answer_relevancy: '答案相关性',
    };
    return metricNames[metric] || metric;
  };

  const getMetricDescription = (metric: string) => {
    const descriptions: { [key: string]: string } = {
      answer_correctness: '衡量生成的答案与标准答案在事实准确性和完整性方面的匹配程度。分数越高表示答案越准确完整。',
      faithfulness: '评估答案对参考上下文的忠实程度，确保答案没有包含上下文中不存在的信息。分数越高表示答案越忠实于原文。',
      context_precision: '衡量检索到的上下文中有用信息的比例。分数越高表示检索的上下文更精准，噪音更少。',
      context_recall: '评估检索系统是否找到了回答问题所需的所有相关信息。分数越高表示检索的上下文覆盖更全面。',
      answer_relevancy: '衡量生成的答案与用户问题的相关程度。分数越高表示答案更贴切地回应了用户的问题。',
    };
    return descriptions[metric] || '该指标用于评估RAG系统的性能表现';
  };

  const getComprehensiveScoreDescription = () => {
    return '基于所有评测指标的加权平均分，综合反映RAG系统在准确性、相关性、忠实度等方面的整体表现。分数范围0-100，越高表示系统性能越优秀。';
  };

  const [selectedReport, setSelectedReport] = useState<EvaluationReport | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'detail'>('list');
  const [reports, setReports] = useState<ApiReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [samples, setSamples] = useState<DatasetSample[]>([]);
  const [samplesLoading, setSamplesLoading] = useState(false);
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<any[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('all');

  // 获取知识库列表
  const fetchKnowledgeBases = async () => {
    try {
      const response = await chatApi.list({ page: 1, page_size: 100 });
      if (response.code === 0 && response.data) {
        setKnowledgeBases(Array.isArray(response.data) ? response.data : []);
      }
    } catch (error) {
      console.error('Failed to fetch knowledge bases:', error);
      message.error('获取知识库列表失败');
    }
  };

  useEffect(() => {
    fetchReports();
    fetchKnowledgeBases();

    return () => {
      // 清理定时器
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // 监听 reports 变化，动态管理定时刷新
  useEffect(() => {
    const hasRunningTasks = reports.some(report => report.status === 'running');

    if (hasRunningTasks && !intervalRef.current) {
      // 有运行中的任务且没有定时器，创建定时器
      intervalRef.current = setInterval(() => {
        fetchReports(true);
      }, 3000); // 每3秒刷新一次
    } else if (!hasRunningTasks && intervalRef.current) {
      // 没有运行中的任务且有时钟器，清除定时器
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [reports]);

  // 监听知识库筛选变化
  useEffect(() => {
    fetchReports();
  }, [selectedKbId]);

  const fetchReports = async (isAutoRefresh = false) => {
    // 如果是自动刷新，不显示加载状态
    if (!isAutoRefresh) {
      setLoading(true);
    }
    try {
      // 构建查询参数
      const params: any = {};
      if (selectedKbId && selectedKbId !== 'all') {
        params.kb_id = selectedKbId;
      }

      const response = await reportApi.list(params);
      const reportsList = Array.isArray(response) ? response : [];
      setReports(reportsList);

      // 检查是否有运行中的任务
      const hasRunningTasks = reportsList.some(report => report.status === 'running');

      // 如果没有运行中的任务且正在自动刷新，停止刷新
      if (isAutoRefresh && !hasRunningTasks) {
        // 可以在这里停止定时刷新的逻辑，但需要使用 ref 来管理 interval
      }
    } catch (error) {
      console.error('Failed to fetch reports:', error);
      message.error('获取报告列表失败');
    } finally {
      if (!isAutoRefresh) {
        setLoading(false);
      }
    }
  };

  const fetchReportSamples = async (datasetId: string) => {
    setSamplesLoading(true);
    try {
      const response = await datasetApi.getSamples(datasetId, { limit: 50 });
      setSamples(response.samples || []);
    } catch (error) {
      console.error('Failed to fetch samples:', error);
      message.error('获取样本数据失败');
    } finally {
      setSamplesLoading(false);
    }
  };

  // 使用统一的批量删除 Hook
  const {
    rowSelection,
    batchDeleting,
    handleBatchDelete,
    clearSelection,
    selectedRowKeys,
  } = useBatchDelete({
    apiCall: reportApi.batchDelete,
    itemName: '评测报告',
    onSuccess: fetchReports,
    permanentWarning: true,
  });

  const columns: ColumnsType<ApiReport> = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 150,
      render: (text, record) => (
        <a onClick={() => showReportDetail(record)} style={{ fontFamily: 'monospace' }}>
          {text.substring(0, 8)}...
        </a>
      ),
    },
    {
      title: '知识库',
      dataIndex: 'kb_name',
      key: 'kb_name',
      width: 200,
      ellipsis: true,
      render: (text) => <Tooltip title={text}>{text}</Tooltip>,
    },
    {
      title: '数据集',
      dataIndex: 'dataset_name',
      key: 'dataset_name',
      width: 200,
      ellipsis: true,
      render: (text) => <Tooltip title={text}>{text}</Tooltip>,
    },
    {
      title: (
        <span>
          综合评分
          <Tooltip title={getComprehensiveScoreDescription()}>
            <QuestionCircleOutlined style={{ marginLeft: 4, color: '#1890ff' }} />
          </Tooltip>
        </span>
      ),
      dataIndex: 'overall_score',
      key: 'overall_score',
      width: 150,
      render: (score) => {
        const scorePercent = score * 100;
        const color = scorePercent >= 80 ? '#52c41a' : scorePercent >= 60 ? '#faad14' : '#ff4d4f';
        return (
          <div>
            <Progress
              percent={Math.round(scorePercent)}
              strokeColor={color}
              size="small"
              format={(percent) => `${percent}分`}
            />
          </div>
        );
      },
      sorter: (a, b) => a.overall_score - b.overall_score,
    },
    {
      title: '样本数',
      dataIndex: 'totalSamples',
      key: 'totalSamples',
      width: 100,
      render: (count) => count || 0,
    },
    {
      title: '生成时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (date: string) => {
        if (!date) return '-';
        try {
          return new Date(date).toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          });
        } catch (error) {
          console.error('Date parsing error:', error);
          return date;
        }
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => showReportDetail(record)}
          >
            查看
          </Button>
        </Space>
      ),
    },
  ];

  const showReportDetail = async (report: ApiReport) => {
    try {
      // 获取报告的详细数据，包括样本评测结果
      const detailResponse = await reportApi.get(report.task_id);
      setSelectedReport(detailResponse as EvaluationReport);
    } catch (error) {
      console.error('Failed to fetch report detail:', error);
      // 如果获取详情失败，使用基本信息
      setSelectedReport(report as EvaluationReport);
    }
    setViewMode('detail');
  };

  const getScoreLevel = (score: number) => {
    if (score >= 90) return { text: '优秀', color: '#52c41a', icon: <TrophyOutlined /> };
    if (score >= 80) return { text: '良好', color: '#1890ff', icon: <CheckCircleOutlined /> };
    if (score >= 60) return { text: '及格', color: '#faad14', icon: <InfoCircleOutlined /> };
    return { text: '待改进', color: '#ff4d4f', icon: <AlertOutlined /> };
  };

  // 获取真实的样本数据，如果没有则返回空数组
  const getRealSampleData = () => {
    if (selectedReport && selectedReport.detailed_scores) {
      return selectedReport.detailed_scores;
    }
    return [];
  };

  const renderReportDetail = () => {
    if (!selectedReport) return null;

    const scorePercent = selectedReport.overall_score * 100;
    const scoreLevel = getScoreLevel(scorePercent);
    const realSamples = getRealSampleData();

    return (
      <div>
        <Card>
          <Row gutter={16}>
            <Col span={16}>
              <Title level={3}>评测报告 - {selectedReport.task_id}</Title>
              <Paragraph type="secondary">
                知识库：{selectedReport.kb_name} | 数据集：{selectedReport.dataset_name}
                <br />
                生成时间：{selectedReport.createdAt ? new Date(selectedReport.createdAt).toLocaleString('zh-CN') : '-'}
              </Paragraph>
            </Col>
            <Col span={8} style={{ textAlign: 'right' }}>
              <Space>
                <Button icon={<ShareAltOutlined />}>分享报告</Button>
                <Button icon={<PrinterOutlined />}>打印</Button>
              </Space>
            </Col>
          </Row>
        </Card>

        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col span={12}>
            <Card>
              <Statistic
                title={
                  <span>
                    综合评分
                    <Tooltip title={getComprehensiveScoreDescription()}>
                      <QuestionCircleOutlined style={{ marginLeft: 4, color: '#1890ff' }} />
                    </Tooltip>
                  </span>
                }
                value={Math.round(scorePercent)}
                suffix="/100"
                prefix={scoreLevel.icon}
                valueStyle={{ color: scoreLevel.color }}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card>
              <Statistic
                title="样本总数"
                value={selectedReport.totalSamples || 0}
                prefix={<FileTextOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* 评测指标详情 */}
        <Card title="评测指标详情" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            {Object.entries(selectedReport.metric_scores || {}).map(([metric, scores]) => (
              <Col span={8} key={metric} style={{ marginBottom: 16 }}>
                <Card size="small" title={
                  <span>
                    {getMetricDisplayName(metric)}
                    <Tooltip title={getMetricDescription(metric)}>
                      <QuestionCircleOutlined style={{ marginLeft: 4, color: '#1890ff' }} />
                    </Tooltip>
                  </span>
                }>
                  <Row gutter={8}>
                    <Col span={12}>
                      <Statistic
                        title="平均值"
                        value={scores.mean || 0}
                        precision={3}
                        valueStyle={{ fontSize: '18px', color: '#1890ff' }}
                      />
                    </Col>
                    <Col span={12}>
                      <Statistic
                        title="标准差"
                        value={scores.std || 0}
                        precision={3}
                        valueStyle={{ fontSize: '14px', color: '#666' }}
                      />
                    </Col>
                  </Row>
                  <Row gutter={8} style={{ marginTop: 8 }}>
                    <Col span={12}>
                      <Text type="secondary">最小值: {(scores.min || 0).toFixed(3)}</Text>
                    </Col>
                    <Col span={12}>
                      <Text type="secondary">最大值: {(scores.max || 0).toFixed(3)}</Text>
                    </Col>
                  </Row>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        {/* 样本详情 */}
        <Card title="样本评测详情" style={{ marginTop: 16 }}>
          {realSamples.length > 0 ? (
            <Table
              dataSource={realSamples}
              scroll={{ x: 'max-content', y: 500 }}
              rowKey={(record, index) => record.user_input?.substring(0, 20) || index?.toString() || Math.random().toString()}
              columns={[
              {
                title: '问题',
                dataIndex: 'user_input',
                key: 'user_input',
                width: 300,
                render: (text) => (
                  <Tooltip title={text}>
                    <Text ellipsis style={{ maxWidth: 280 }}>{text}</Text>
                  </Tooltip>
                ),
              },
              // 动态生成指标列
              ...Object.keys(realSamples[0] || {})
                .filter(key => key !== 'user_input' && key !== 'actual_answer' && key !== 'expected_answer' && key !== 'contexts' && typeof realSamples[0][key] === 'number')
                .map(metric => ({
                  title: (
                    <span>
                      {getMetricDisplayName(metric)}
                      <Tooltip title={getMetricDescription(metric)}>
                        <QuestionCircleOutlined style={{ marginLeft: 4, color: '#1890ff' }} />
                      </Tooltip>
                    </span>
                  ),
                  dataIndex: metric,
                  key: metric,
                  width: 120,
                  render: (score: number) => {
                    const percent = score * 100;
                    const color = percent >= 80 ? '#52c41a' : percent >= 60 ? '#faad14' : '#ff4d4f';
                    return (
                      <Progress
                        percent={Math.round(percent)}
                        strokeColor={color}
                        size="small"
                        format={(percent) => `${percent}%`}
                      />
                    );
                  },
                  sorter: (a: any, b: any) => a[metric] - b[metric],
                })),
              {
                title: '操作',
                key: 'action',
                width: 80,
                fixed: 'right',
                render: (_, record, index) => (
                  <Button
                    type="link"
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={() => {
                      // 获取当前行的唯一 key
                      const key = record.user_input?.substring(0, 20) || Math.random().toString();

                      // 判断当前行是否已展开
                      const isExpanded = expandedRowKeys.includes(key);

                      if (isExpanded) {
                        // 如果已展开，则收起
                        setExpandedRowKeys([]);
                      } else {
                        // 如果未展开，则展开当前行并收起其他行
                        setExpandedRowKeys([key]);
                      }
                    }}
                  >
                    详情
                  </Button>
                ),
              },
            ]}
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 个样本`,
            }}
            size="small"
            expandable={{
              expandedRowRender: (record) => (
                <div style={{
                  margin: 0,
                  maxWidth: '100%',
                  overflow: 'hidden',
                  width: '100%',
                  tableLayout: 'fixed'
                }}>
                  <div style={{ width: '100%', overflow: 'hidden' }}>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Title level={5}>实际回答</Title>
                        <div style={{
                          backgroundColor: '#f6f8fa',
                          padding: 12,
                          borderRadius: 4,
                          height: '300px',
                          overflow: 'auto',
                          wordBreak: 'break-word',
                          whiteSpace: 'pre-wrap',
                          width: '100%',
                          boxSizing: 'border-box'
                        }}>
                          <Text>{record.actual_answer}</Text>
                        </div>
                      </Col>
                      <Col span={12}>
                        <Title level={5}>预期答案</Title>
                        <div style={{
                          backgroundColor: '#fff2e8',
                          padding: 12,
                          borderRadius: 4,
                          height: '300px',
                          overflow: 'auto',
                          wordBreak: 'break-word',
                          whiteSpace: 'pre-wrap',
                          width: '100%',
                          boxSizing: 'border-box'
                        }}>
                          <Text>{record.expected_answer}</Text>
                        </div>
                      </Col>
                    </Row>
                    <Row gutter={16} style={{ marginTop: 16 }}>
                      <Col span={24}>
                        <Title level={5}>参考上下文</Title>
                        <div style={{
                          height: '200px',
                          overflow: 'auto',
                          wordBreak: 'break-word',
                          width: '100%'
                        }}>
                          {record.contexts.map((context, idx) => (
                            <Tag key={idx} style={{
                              marginBottom: 4,
                              marginRight: 8,
                              display: 'inline-block',
                              maxWidth: '100%',
                              wordBreak: 'break-word'
                            }}>{context}</Tag>
                          ))}
                        </div>
                      </Col>
                    </Row>
                  </div>
                </div>
              ),
              rowExpandable: () => true,
              expandedRowKeys: expandedRowKeys,
              onExpand: (expanded, record) => {
                // 使用问题的前20个字符作为 key，确保唯一性
                const key = record.user_input?.substring(0, 20) || Math.random().toString();
                if (expanded) {
                  // 只展开当前点击的行，收起其他行
                  setExpandedRowKeys([key]);
                } else {
                  // 收起当前行
                  setExpandedRowKeys(expandedRowKeys.filter(k => k !== key));
                }
              },
              }}
          />
            ) : (
              <Empty description="暂无详细样本数据" />
            )}
        </Card>

        {/* 改进建议 */}
        {selectedReport.recommendations && selectedReport.recommendations.length > 0 && (
          <Card title="改进建议" style={{ marginTop: 16 }}>
            <List
              dataSource={selectedReport.recommendations}
              renderItem={(item, index) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<BulbOutlined style={{ color: '#faad14', fontSize: 20 }} />}
                    description={<Text>{item}</Text>}
                  />
                </List.Item>
              )}
            />
          </Card>
        )}

        {/* 低分样本分析 */}
        {selectedReport.lowScoreSamples && selectedReport.lowScoreSamples.length > 0 && (
          <Card title="低分样本分析" style={{ marginTop: 16 }}>
            <Timeline>
              {selectedReport.lowScoreSamples.map((sample, index) => (
                <Timeline.Item
                  key={index}
                  color={sample.score < 0.3 ? 'red' : sample.score < 0.6 ? 'orange' : 'blue'}
                >
                  <Text strong>问题: {sample.question}</Text>
                  <br />
                  <Text type="danger">得分: {Math.round(sample.score * 100)}% - {sample.issue}</Text>
                </Timeline.Item>
              ))}
            </Timeline>
          </Card>
        )}
      </div>
    );
  };

  return (
    <div>
      <Title level={2}>评测报告</Title>

      {viewMode === 'list' ? (
        <>
          <Card style={{ marginTop: 24 }}>
            <div style={{ marginBottom: 16 }}>
              <Space>
                <RangePicker />
                <Select
                  value={selectedKbId}
                  onChange={(value) => setSelectedKbId(value)}
                  style={{ width: 200 }}
                  placeholder="选择知识库"
                >
                  <Select.Option value="all">所有知识库</Select.Option>
                  {knowledgeBases.map((kb) => (
                    <Select.Option key={kb.id} value={kb.id}>
                      {kb.name}
                    </Select.Option>
                  ))}
                </Select>
              </Space>
            </div>

            <BatchActionBar
              selectedCount={selectedRowKeys.length}
              onDelete={handleBatchDelete}
              onCancel={clearSelection}
              deleting={batchDeleting}
              itemName="评测报告"
            />

            <Table
              columns={columns}
              dataSource={reports}
              loading={loading}
              rowKey="task_id"
              rowSelection={rowSelection}
              scroll={{ x: 1200 }}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `共 ${total} 份报告`,
              }}
              locale={{ emptyText: '暂无评测报告' }}
            />
          </Card>

          </>
      ) : (
        <>
          <Button
            onClick={() => setViewMode('list')}
            style={{ marginBottom: 16 }}
          >
            返回列表
          </Button>
          {renderReportDetail()}
        </>
      )}
    </div>
  );
};

export default Reports;