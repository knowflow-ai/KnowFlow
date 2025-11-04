import React, { useState, useEffect } from 'react';
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
  Radio,
  Tabs,
  List,
  Avatar,
  Badge,
  Spin,
  message,
} from 'antd';
import {
  FileTextOutlined,
  DownloadOutlined,
  ShareAltOutlined,
  PrinterOutlined,
  FilePdfOutlined,
  FileExcelOutlined,
  LineChartOutlined,
  BarChartOutlined,
  PieChartOutlined,
  TrophyOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  RiseOutlined,
  FallOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { reportApi } from '../services/evaluation';
import type { EvaluationReport as ApiReport } from '../services/evaluation';

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;
const { TabPane } = Tabs;

interface EvaluationReport {
  id: string;
  taskId: string;
  taskName: string;
  kbName: string;
  datasetName: string;
  overallScore: number;
  healthScore: number;
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
  successRate: number;
  recommendations: string[];
  lowScoreSamples: Array<{
    question: string;
    score: number;
    issue: string;
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
  const [selectedReport, setSelectedReport] = useState<ApiReport | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'detail'>('list');
  const [reports, setReports] = useState<ApiReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const response = await reportApi.list();
      setReports(Array.isArray(response) ? response : []);
    } catch (error) {
      console.error('Failed to fetch reports:', error);
      message.error('获取报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<ApiReport> = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      render: (text, record) => (
        <a onClick={() => showReportDetail(record)}>{text}</a>
      ),
    },
    {
      title: '知识库',
      dataIndex: 'kb_name',
      key: 'kb_name',
    },
    {
      title: '数据集',
      dataIndex: 'dataset_name',
      key: 'dataset_name',
    },
    {
      title: '综合评分',
      dataIndex: 'overall_score',
      key: 'overall_score',
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
      title: '健康度',
      dataIndex: 'health_score',
      key: 'health_score',
      render: (score) => {
        const level = score >= 80 ? '优秀' : score >= 60 ? '良好' : '待改进';
        const color = score >= 80 ? 'green' : score >= 60 ? 'orange' : 'red';
        return <Tag color={color}>{level}</Tag>;
      },
    },
    {
      title: '样本数',
      dataIndex: 'totalSamples',
      key: 'totalSamples',
    },
    {
      title: '成功率',
      dataIndex: 'successRate',
      key: 'successRate',
      render: (rate) => `${rate}%`,
    },
    {
      title: '生成时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<FileTextOutlined />}
            onClick={() => showReportDetail(record)}
          >
            查看
          </Button>
          <Tooltip title="下载PDF">
            <Button size="small" icon={<FilePdfOutlined />} />
          </Tooltip>
          <Tooltip title="下载Excel">
            <Button size="small" icon={<FileExcelOutlined />} />
          </Tooltip>
          <Tooltip title="分享">
            <Button size="small" icon={<ShareAltOutlined />} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const showReportDetail = (report: EvaluationReport) => {
    setSelectedReport(report);
    setViewMode('detail');
  };

  const getScoreLevel = (score: number) => {
    if (score >= 90) return { text: '优秀', color: '#52c41a', icon: <TrophyOutlined /> };
    if (score >= 80) return { text: '良好', color: '#1890ff', icon: <CheckCircleOutlined /> };
    if (score >= 60) return { text: '及格', color: '#faad14', icon: <InfoCircleOutlined /> };
    return { text: '待改进', color: '#ff4d4f', icon: <AlertOutlined /> };
  };

  const renderReportDetail = () => {
    if (!selectedReport) return null;

    const scorePercent = selectedReport.overall_score * 100;
    const scoreLevel = getScoreLevel(scorePercent);

    return (
      <div>
        <Card>
          <Row gutter={16}>
            <Col span={16}>
              <Title level={3}>评测报告 - {selectedReport.task_id}</Title>
              <Paragraph type="secondary">
                知识库：{selectedReport.kb_name} | 数据集：{selectedReport.dataset_name}
                <br />
                生成时间：{new Date(selectedReport.created_at).toLocaleString('zh-CN')}
              </Paragraph>
            </Col>
            <Col span={8} style={{ textAlign: 'right' }}>
              <Space>
                <Button icon={<FilePdfOutlined />}>导出PDF</Button>
                <Button icon={<FileExcelOutlined />}>导出Excel</Button>
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
                title="综合评分"
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
                title="健康度"
                value={selectedReport.health_score}
                suffix="/100"
                prefix={<TrophyOutlined />}
              />
            </Card>
          </Col>
        </Row>

        <Card title="评测指标详情" style={{ marginTop: 16 }}>
          <Row gutter={[16, 16]}>
            {Object.entries(selectedReport.metric_scores).map(([key, value]) => {
              const metricName = {
                faithfulness: '忠实度',
                answer_correctness: '答案正确性',
                context_precision: '上下文精准度',
                context_recall: '上下文召回率',
              }[key] || key;

              return (
                <Col span={12} key={key}>
                  <Card size="small">
                    <Title level={5}>{metricName}</Title>
                    <Row gutter={16}>
                      <Col span={6}>
                        <Statistic
                          title="平均值"
                          value={value.mean}
                          precision={2}
                          valueStyle={{ fontSize: 14 }}
                        />
                      </Col>
                      <Col span={6}>
                        <Statistic
                          title="标准差"
                          value={value.std}
                          precision={2}
                          valueStyle={{ fontSize: 14 }}
                        />
                      </Col>
                      <Col span={6}>
                        <Statistic
                          title="最小值"
                          value={value.min}
                          precision={2}
                          valueStyle={{ fontSize: 14 }}
                        />
                      </Col>
                      <Col span={6}>
                        <Statistic
                          title="最大值"
                          value={value.max}
                          precision={2}
                          valueStyle={{ fontSize: 14 }}
                        />
                      </Col>
                    </Row>
                    <Progress
                      percent={value.mean * 100}
                      strokeColor={{
                        '0%': '#108ee9',
                        '100%': '#87d068',
                      }}
                      showInfo={false}
                      style={{ marginTop: 8 }}
                    />
                  </Card>
                </Col>
              );
            })}
          </Row>
        </Card>

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col span={12}>
            <Card title="优化建议" extra={<InfoCircleOutlined />}>
              <List
                dataSource={selectedReport.recommendations}
                renderItem={(item, index) => (
                  <List.Item>
                    <Space>
                      <Badge count={index + 1} style={{ backgroundColor: '#1890ff' }} />
                      <Text>{item}</Text>
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card title="低分样本分析" extra={<AlertOutlined style={{ color: '#ff4d4f' }} />}>
              <List
                dataSource={selectedReport.lowScoreSamples}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={
                        <Avatar
                          style={{
                            backgroundColor: '#ff4d4f',
                            fontSize: 12,
                          }}
                        >
                          {item.score.toFixed(1)}
                        </Avatar>
                      }
                      title={item.question}
                      description={
                        <Space>
                          <Tag color="red">{item.issue}</Tag>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
              {selectedReport.lowScoreSamples.length === 0 && (
                <Empty description="暂无低分样本" />
              )}
            </Card>
          </Col>
        </Row>

        <Card title="评测趋势" style={{ marginTop: 16 }}>
          <Alert
            message="趋势图表"
            description="评测指标的历史趋势图将在集成图表库后显示"
            type="info"
            showIcon
          />
        </Card>
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
                <Select defaultValue="all" style={{ width: 120 }}>
                  <Select.Option value="all">所有知识库</Select.Option>
                  <Select.Option value="finance">金融知识库</Select.Option>
                  <Select.Option value="medical">医疗知识库</Select.Option>
                  <Select.Option value="law">法律知识库</Select.Option>
                </Select>
                <Radio.Group defaultValue="table">
                  <Radio.Button value="table">表格视图</Radio.Button>
                  <Radio.Button value="card">卡片视图</Radio.Button>
                </Radio.Group>
              </Space>
            </div>

            <Table
              columns={columns}
              dataSource={reports}
              loading={loading}
              rowKey="task_id"
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `共 ${total} 份报告`,
              }}
              locale={{ emptyText: '暂无评测报告' }}
            />
          </Card>

          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={12}>
              <Card title="评测指标趋势">
                <Empty description="趋势图表待集成" />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="知识库对比">
                <Empty description="对比图表待集成" />
              </Card>
            </Col>
          </Row>
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