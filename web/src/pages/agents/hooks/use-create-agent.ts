import { useSetModalState } from '@/hooks/common-hooks';
import { useSetFlow } from '@/hooks/flow-hooks';
import { EmptyDsl, useSetAgent } from '@/hooks/use-agent-request';
import { DSL } from '@/interfaces/database/agent';
import { DSL as FlowDSL } from '@/interfaces/database/flow';
import { useCallback } from 'react';
import { useNavigate } from 'umi';
import { FlowType } from '../constant';
import { FormSchemaType } from '../create-agent-form';

export function useCreateAgentOrPipeline() {
  const { loading: agentLoading, setAgent } = useSetAgent();
  const { loading: flowLoading, setFlow } = useSetFlow();
  const navigate = useNavigate();
  const {
    visible: creatingVisible,
    hideModal: hideCreatingModal,
    showModal: showCreatingModal,
  } = useSetModalState();

  const loading = agentLoading || flowLoading;

  const createAgent = useCallback(
    async (name: string) => {
      return setAgent({ title: name, dsl: EmptyDsl as DSL });
    },
    [setAgent],
  );

  const createFlow = useCallback(
    async (name: string) => {
      const { EmptyDsl: FlowEmptyDsl } = await import('@/hooks/flow-hooks');
      return setFlow({ title: name, dsl: FlowEmptyDsl as FlowDSL });
    },
    [setFlow],
  );

  const handleCreateAgentOrPipeline = useCallback(
    async (data: FormSchemaType) => {
      if (data.type === FlowType.Agent) {
        const ret = await createAgent(data.name);
        if (ret.code === 0) {
          hideCreatingModal();
          navigate(`/agent/${ret.data.id}`);
        }
      } else if (data.type === FlowType.Flow) {
        const ret = await createFlow(data.name);
        if (ret.code === 0) {
          hideCreatingModal();
          navigate(`/flow/${ret.data.id}`);
        }
      }
    },
    [createAgent, createFlow, hideCreatingModal, navigate],
  );

  return {
    loading,
    creatingVisible,
    hideCreatingModal,
    showCreatingModal,
    handleCreateAgentOrPipeline,
  };
}
